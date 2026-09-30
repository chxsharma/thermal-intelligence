"""Build deterministic FIRMS-like demo observations."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCENARIOS = {
    "scenario-refinery-persistent": {
        "lat": 22.3751,
        "lon": 69.8610,
        "sensor": "VIIRS",
        "satellite": "NOAA-20",
        "dataset": "VIIRS_NOAA20_NRT",
        "quality": "nominal",
        "spread_m": 0.0012,
    },
    "scenario-industrial-suspicious": {
        "lat": 17.6924,
        "lon": 83.2210,
        "sensor": "VIIRS",
        "satellite": "Suomi NPP",
        "dataset": "VIIRS_SNPP_NRT",
        "quality": "nominal",
        "spread_m": 0.0018,
    },
    "scenario-vegetation-fire": {
        "lat": 29.3920,
        "lon": 79.4560,
        "sensor": "MODIS",
        "satellite": "Aqua",
        "dataset": "MODIS_NRT",
        "quality": "nominal",
        "spread_m": 0.012,
    },
    "scenario-agricultural-burning": {
        "lat": 30.9012,
        "lon": 75.8574,
        "sensor": "VIIRS",
        "satellite": "NOAA-20",
        "dataset": "VIIRS_NOAA20_NRT",
        "quality": "nominal",
        "spread_m": 0.008,
    },
    "scenario-uncertain-hotspot": {
        "lat": 26.9120,
        "lon": 71.0040,
        "sensor": "VIIRS",
        "satellite": "Suomi NPP",
        "dataset": "VIIRS_SNPP_NRT",
        "quality": "low",
        "spread_m": 0.002,
    },
    "scenario-conflicting-evidence": {
        "lat": 18.6295,
        "lon": 73.8012,
        "sensor": "VIIRS",
        "satellite": "NOAA-20",
        "dataset": "VIIRS_NOAA20_NRT",
        "quality": "nominal",
        "spread_m": 0.006,
    },
}


def _obs(i: int, scenario: str, when: datetime, lat: float, lon: float, **kwargs) -> dict:
    spec = SCENARIOS[scenario]
    rec = {
        "id": f"OBS-{scenario.split('-', 1)[1].upper()[:8]}-{i:03d}",
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "acquired_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brightness": kwargs.get("brightness"),
        "frp": kwargs.get("frp"),
        "confidence": kwargs.get("confidence"),
        "sensor": spec["sensor"],
        "satellite": spec["satellite"],
        "day_night": kwargs.get("day_night"),
        "scan": kwargs.get("scan", 1.0),
        "track": kwargs.get("track", 1.0),
        "source_dataset": spec["dataset"],
        "observation_quality": spec["quality"],
        "scenario_id": scenario,
        "source": "demo",
        "provenance": {
            "provider": "DemoDataProvider",
            "dataset_version": "demo-replay-2026.09",
            "processed_at": "2026-09-13T12:00:00Z",
        },
    }
    return rec


def build() -> list[dict]:
    rows: list[dict] = []
    t0 = datetime(2026, 6, 15, 18, 12, tzinfo=timezone.utc)

    # 1 Persistent refinery: ~40 night-leaning detections over 90 days, tight spatial
    spec = SCENARIOS["scenario-refinery-persistent"]
    n = 0
    for d in range(0, 90, 2):
        n += 1
        jitter = ((n % 5) - 2) * spec["spread_m"] / 2
        night = n % 3 != 1
        rows.append(
            _obs(
                n,
                "scenario-refinery-persistent",
                t0 + timedelta(days=d, hours=4 if night else -8),
                spec["lat"] + jitter,
                spec["lon"] - jitter / 2,
                brightness=340 + (n % 6),
                frp=18.0 + (n % 5) * 1.4,
                confidence="h" if n % 4 else "n",
                day_night="N" if night else "D",
            )
        )

    # 2 Suspicious industrial: 8 detections in 36h, rising FRP
    spec = SCENARIOS["scenario-industrial-suspicious"]
    t1 = datetime(2026, 9, 10, 16, 0, tzinfo=timezone.utc)
    for i, hours in enumerate([0, 3, 6, 9, 14, 18, 26, 32], start=1):
        rows.append(
            _obs(
                i,
                "scenario-industrial-suspicious",
                t1 + timedelta(hours=hours),
                spec["lat"] + (i - 4) * 0.0004,
                spec["lon"] + (i % 3) * 0.0003,
                brightness=345 + i * 2,
                frp=12 + i * 6.5,
                confidence="n" if i < 3 else "h",
                day_night="D" if hours < 12 or 24 <= hours < 30 else "N",
            )
        )

    # 3 Vegetation fire: spreading, 15 obs / 4 days
    spec = SCENARIOS["scenario-vegetation-fire"]
    t2 = datetime(2026, 9, 8, 6, 20, tzinfo=timezone.utc)
    for i in range(1, 16):
        rows.append(
            _obs(
                i,
                "scenario-vegetation-fire",
                t2 + timedelta(hours=i * 6),
                spec["lat"] + i * 0.0035,
                spec["lon"] + (i % 4) * 0.0025,
                brightness=330 + (i % 8),
                frp=8 + i * 1.1,
                confidence="n",
                day_night="D" if i % 2 else "N",
            )
        )

    # 4 Agricultural: day-heavy, 12 obs / 3 days
    spec = SCENARIOS["scenario-agricultural-burning"]
    t3 = datetime(2026, 9, 11, 4, 40, tzinfo=timezone.utc)
    for i in range(1, 13):
        rows.append(
            _obs(
                i,
                "scenario-agricultural-burning",
                t3 + timedelta(hours=5 * i if i < 8 else 4 * i),
                spec["lat"] + (i % 5) * 0.002,
                spec["lon"] + ((i * 3) % 4) * 0.0022,
                brightness=325 + i,
                frp=6.0 + i * 0.4,
                confidence="n" if i % 2 else "l",
                day_night="D" if i % 5 else "N",
            )
        )

    # 5 Uncertain: single observation, missing FRP and confidence
    spec = SCENARIOS["scenario-uncertain-hotspot"]
    rows.append(
        _obs(
            1,
            "scenario-uncertain-hotspot",
            datetime(2026, 9, 12, 21, 4, tzinfo=timezone.utc),
            spec["lat"],
            spec["lon"],
            brightness=318,
            frp=None,
            confidence=None,
            day_night="N",
            scan=None,
            track=None,
        )
    )

    # 6 Conflicting: 10 obs, near industry, mixed land, short window
    spec = SCENARIOS["scenario-conflicting-evidence"]
    t5 = datetime(2026, 9, 9, 11, 0, tzinfo=timezone.utc)
    for i in range(1, 11):
        rows.append(
            _obs(
                i,
                "scenario-conflicting-evidence",
                t5 + timedelta(hours=8 * i),
                spec["lat"] + (i - 5) * 0.0015,
                spec["lon"] + ((i % 3) - 1) * 0.0012,
                brightness=336 + i,
                frp=14 + (i % 4) * 3,
                confidence="n",
                day_night="D" if i % 2 else "N",
            )
        )
    return rows


def main() -> None:
    rows = build()
    (ROOT / "observations.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    fieldnames = [
        "latitude",
        "longitude",
        "acq_date",
        "acq_time",
        "bright_ti4",
        "frp",
        "confidence",
        "daynight",
        "satellite",
        "instrument",
        "scan",
        "track",
    ]
    with (ROOT / "firms_sample.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows[:25]:
            acquired = datetime.fromisoformat(row["acquired_at"].replace("Z", "+00:00"))
            writer.writerow(
                {
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "acq_date": acquired.date().isoformat(),
                    "acq_time": acquired.strftime("%H%M"),
                    "bright_ti4": row["brightness"] if row["brightness"] is not None else "",
                    "frp": row["frp"] if row["frp"] is not None else "",
                    "confidence": row["confidence"] if row["confidence"] is not None else "",
                    "daynight": row["day_night"] or "",
                    "satellite": row["satellite"] or "",
                    "instrument": row["sensor"] or "",
                    "scan": row["scan"] if row["scan"] is not None else "",
                    "track": row["track"] if row["track"] is not None else "",
                }
            )
    print(f"wrote {len(rows)} observations")


if __name__ == "__main__":
    main()
