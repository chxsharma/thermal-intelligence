from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.geo import haversine_m
from app.providers.base import ContextProvider, DataProvider, parse_observation
from app.schemas.domain import IndustrialFacility, ThermalObservation

FIRMS_AREA_CSV = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_DATA_AVAILABILITY = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"
HISTORICAL_WINDOWS_DAYS = (30, 60, 90)
NRT_MAX_DAYS = 5
AREA_CHUNK_DAYS = 5
# Programmatic equivalent of FIRMS Archive Download for a bbox + date range.
ARCHIVE_METHOD = "firms_area_api_dated"


class LiveFIRMSProvider(DataProvider):
    """Current Area API NRT pull: no DATE path segment. Not used for archive history."""

    name = "LiveFIRMSProvider"
    mode = "LIVE"

    def fetch_observations(self) -> list[ThermalObservation]:
        settings = get_settings()
        if not settings.firms_map_key:
            raise RuntimeError("FIRMS_MAP_KEY is not configured")
        west, south, east, north = [p.strip() for p in settings.firms_bbox.split(",")]
        # NASA FIRMS Area API accepts DAY_RANGE 1..5 only for the NRT live pull.
        day_range = max(1, min(int(settings.firms_days), NRT_MAX_DAYS))
        url = (
            f"{FIRMS_AREA_CSV}/"
            f"{settings.firms_map_key}/{settings.firms_source}/{west},{south},{east},{north}/{day_range}"
        )
        response = httpx.get(url, timeout=60.0)
        if response.is_error:
            detail = (response.text or response.reason_phrase or "").strip()[:400]
            raise RuntimeError(f"FIRMS request failed ({response.status_code}): {detail}")
        ingested = datetime.now(timezone.utc).isoformat()
        return parse_firms_csv(
            response.text,
            provenance_extra={
                "provider": "LiveFIRMSProvider",
                "mode": "live",
                "firms_source": settings.firms_source,
                "processing": "nrt_current",
                "ingested_at": ingested,
            },
        )


class HistoricalFIRMSProvider:
    """Archived NRT via FIRMS Area API + DATE. Clipped to official data_availability."""

    name = "HistoricalFIRMSProvider"
    mode = "HISTORICAL"

    def __init__(self) -> None:
        self.last_historical_report: dict[str, Any] | None = None

    def fetch_availability(self, source: str) -> tuple[date, date] | None:
        settings = get_settings()
        url = f"{FIRMS_DATA_AVAILABILITY}/{settings.firms_map_key}/{source}"
        response = httpx.get(url, timeout=60.0)
        if response.is_error:
            return None
        return parse_data_availability(response.text or "", source)

    def fetch_historical(
        self,
        *,
        days: int | None = None,
        bbox: str | None = None,
        end_date: date | None = None,
        source: str | None = None,
        use_cache: bool = True,
        chunk_sleep_s: float = 1.0,
        exclude_live_nrt_window: bool = True,
    ) -> list[ThermalObservation]:
        """Opt-in archived-NRT backfill. Not called by live NRT reload."""
        settings = get_settings()
        if not settings.firms_map_key:
            raise RuntimeError("FIRMS_MAP_KEY is not configured")
        window_days = int(days if days is not None else settings.firms_historical_days)
        if window_days < 1:
            raise ValueError("historical days must be >= 1")
        bbox_s = (bbox or settings.firms_historical_bbox).strip()
        src = (source or settings.firms_historical_source).strip()
        today = datetime.now(timezone.utc).date()
        live_days = max(1, min(int(getattr(settings, "firms_days", NRT_MAX_DAYS)), NRT_MAX_DAYS))
        intent_end = end_date or today
        intent_start = intent_end - timedelta(days=window_days - 1)
        processing = processing_label_for_source(src)
        ingested = datetime.now(timezone.utc)
        report: dict[str, Any] = {
            "archive_method": ARCHIVE_METHOD,
            "endpoint": f"{FIRMS_AREA_CSV}/<MAP_KEY>/{src}/<bbox>/{AREA_CHUNK_DAYS}/<YYYY-MM-DD>",
            "availability_endpoint": f"{FIRMS_DATA_AVAILABILITY}/<MAP_KEY>/{src}",
            "data_product": src,
            "processing": processing,
            "bbox": bbox_s,
            "requested_start": intent_start.isoformat(),
            "requested_end": intent_end.isoformat(),
            "query_start": None,
            "query_end": None,
            "availability_min": None,
            "availability_max": None,
            "cache_hit": False,
            "cache_path": None,
            "http_requests": 0,
            "availability_http": 0,
            "area_http": 0,
            "errors": [],
            "record_count": 0,
            "actual_start": None,
            "actual_end": None,
        }

        try:
            avail = self.fetch_availability(src)
        except httpx.HTTPError as exc:
            report["errors"].append(f"availability: {exc.__class__.__name__}")
            self._finish_historical_report(report, [])
            self.last_historical_report = report
            return []
        report["http_requests"] += 1
        report["availability_http"] = 1
        if avail is None:
            report["errors"].append("availability: unusable response; no archive dates requested")
            self._finish_historical_report(report, [])
            self.last_historical_report = report
            return []
        avail_min, avail_max = avail
        report["availability_min"] = avail_min.isoformat()
        report["availability_max"] = avail_max.isoformat()

        query_start, query_end = resolve_archive_window(
            intent_start,
            intent_end,
            avail_min,
            avail_max,
            today=today,
            live_days=live_days,
            window_days=window_days,
            end_date_explicit=end_date is not None,
            exclude_live_nrt_window=exclude_live_nrt_window,
        )
        if end_date is None and query_start and query_end:
            report["requested_start"] = query_start.isoformat()
            report["requested_end"] = query_end.isoformat()
        report["query_start"] = query_start.isoformat() if query_start else None
        report["query_end"] = query_end.isoformat() if query_end else None
        if query_start is None or query_end is None:
            report["errors"].append("requested dates do not overlap product availability")
            self._finish_historical_report(report, [])
            self.last_historical_report = report
            return []

        cache_path = historical_cache_path(src, bbox_s, query_start, query_end)
        report["cache_path"] = str(cache_path)
        if use_cache and cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            rows = [ThermalObservation.model_validate(item) for item in payload.get("records", [])]
            rows = filter_by_acquired_window(rows, query_start, query_end)
            report["cache_hit"] = True
            self._finish_historical_report(report, rows)
            self.last_historical_report = report
            return rows

        rows: list[ThermalObservation] = []
        windows = historical_chunk_windows(query_start, query_end, AREA_CHUNK_DAYS)
        for i, (chunk_start, chunk_days) in enumerate(windows):
            if i and chunk_sleep_s:
                time.sleep(chunk_sleep_s)
            url = (
                f"{FIRMS_AREA_CSV}/{settings.firms_map_key}/{src}/"
                f"{bbox_s}/{chunk_days}/{chunk_start.isoformat()}"
            )
            try:
                response = httpx.get(url, timeout=60.0)
            except httpx.HTTPError as exc:
                report["errors"].append(f"{chunk_start.isoformat()}: {exc.__class__.__name__}")
                continue
            report["http_requests"] += 1
            report["area_http"] += 1
            if response.is_error:
                detail = (response.text or response.reason_phrase or "").strip()[:200]
                report["errors"].append(f"{chunk_start.isoformat()}: HTTP {response.status_code} {detail}")
                continue
            text = response.text or ""
            if not text.strip() or "latitude" not in text.splitlines()[0].lower():
                continue
            try:
                chunk = parse_firms_csv(
                    text,
                    provenance_extra={
                        "provider": self.name,
                        "mode": "historical",
                        "firms_source": src,
                        "processing": processing,
                        "archive_method": ARCHIVE_METHOD,
                        "ingested_at": ingested.isoformat(),
                        "requested_start": report["requested_start"],
                        "requested_end": report["requested_end"],
                        "query_start": query_start.isoformat(),
                        "query_end": query_end.isoformat(),
                        "availability_min": avail_min.isoformat(),
                        "availability_max": avail_max.isoformat(),
                        "bbox": bbox_s,
                        "chunk_start": chunk_start.isoformat(),
                    },
                )
            except ValueError as exc:
                report["errors"].append(f"{chunk_start.isoformat()}: {exc}")
                continue
            rows.extend(chunk)

        rows = filter_by_acquired_window(rows, query_start, query_end)
        rows = _dedup_observations(rows)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "data_product": src,
                    "processing": processing,
                    "archive_method": ARCHIVE_METHOD,
                    "bbox": bbox_s,
                    "requested_start": report["requested_start"],
                    "requested_end": report["requested_end"],
                    "query_start": query_start.isoformat(),
                    "query_end": query_end.isoformat(),
                    "availability_min": avail_min.isoformat(),
                    "availability_max": avail_max.isoformat(),
                    "fetched_at": ingested.isoformat(),
                    "records": [o.model_dump(mode="json") for o in rows],
                },
                default=str,
            ),
            encoding="utf-8",
        )
        self._finish_historical_report(report, rows)
        self.last_historical_report = report
        return rows

    def _finish_historical_report(self, report: dict[str, Any], rows: list[ThermalObservation]) -> None:
        report["record_count"] = len(rows)
        if rows:
            times = [o.acquired_at for o in rows]
            report["actual_start"] = min(times).date().isoformat()
            report["actual_end"] = max(times).date().isoformat()
        else:
            report["actual_start"] = None
            report["actual_end"] = None
        query_start = report.get("query_start")
        query_end = report.get("query_end")
        report["covers_requested_window"] = bool(
            rows
            and report["actual_start"] == query_start
            and report["actual_end"] == query_end
        )


class FirmsDataProvider(LiveFIRMSProvider):
    """Live NRT provider used by the pipeline; archive history is opt-in."""

    name = "FirmsDataProvider"

    def __init__(self) -> None:
        self.historical = HistoricalFIRMSProvider()
        self.last_historical_report: dict[str, Any] | None = None

    def fetch_historical(self, **kwargs: Any) -> list[ThermalObservation]:
        rows = self.historical.fetch_historical(**kwargs)
        self.last_historical_report = self.historical.last_historical_report
        return rows


def processing_label_for_source(source: str) -> str:
    src = (source or "").upper()
    if src.endswith("_SP"):
        return "standard_quality"
    if src.endswith("_NRT"):
        return "nrt_archive"
    return "unknown"


def parse_data_availability(text: str, source: str) -> tuple[date, date] | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    header = [h.strip().lower() for h in lines[0].split(",")]
    if "min_date" not in header or "max_date" not in header:
        return None
    want = source.strip().upper()
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(header):
            continue
        raw = dict(zip(header, parts, strict=False))
        data_id = (raw.get("data_id") or raw.get("source") or "").upper()
        if data_id and data_id != want:
            continue
        try:
            return date.fromisoformat(raw["min_date"][:10]), date.fromisoformat(raw["max_date"][:10])
        except ValueError:
            return None
    return None


def clip_archive_window(
    intent_start: date,
    intent_end: date,
    avail_min: date,
    avail_max: date,
    *,
    today: date,
    live_days: int,
    exclude_live_nrt_window: bool,
) -> tuple[date | None, date | None]:
    start = max(intent_start, avail_min)
    end = min(intent_end, avail_max)
    if exclude_live_nrt_window:
        live_start = today - timedelta(days=max(1, live_days) - 1)
        if end >= live_start:
            end = live_start - timedelta(days=1)
    if start > end:
        return None, None
    return start, end


def resolve_archive_window(
    intent_start: date,
    intent_end: date,
    avail_min: date,
    avail_max: date,
    *,
    today: date,
    live_days: int,
    window_days: int,
    end_date_explicit: bool,
    exclude_live_nrt_window: bool,
) -> tuple[date | None, date | None]:
    """Explicit end_date: intersect only. Default: latest full window older than live NRT."""
    if end_date_explicit:
        return clip_archive_window(
            intent_start,
            intent_end,
            avail_min,
            avail_max,
            today=today,
            live_days=live_days,
            exclude_live_nrt_window=exclude_live_nrt_window,
        )
    end = min(today, avail_max)
    if exclude_live_nrt_window:
        live_start = today - timedelta(days=max(1, live_days) - 1)
        if end >= live_start:
            end = live_start - timedelta(days=1)
    start = end - timedelta(days=max(1, window_days) - 1)
    start = max(start, avail_min)
    if start > end:
        return None, None
    return start, end


def historical_chunk_windows(start: date, end: date, chunk_days: int = AREA_CHUNK_DAYS) -> list[tuple[date, int]]:
    windows: list[tuple[date, int]] = []
    cursor = start
    chunk_days = max(1, min(int(chunk_days), AREA_CHUNK_DAYS))
    while cursor <= end:
        remaining = (end - cursor).days + 1
        span = min(chunk_days, remaining)
        windows.append((cursor, span))
        cursor = cursor + timedelta(days=span)
    return windows


def historical_cache_path(source: str, bbox: str, start: date, end: date) -> Path:
    from app.config import ROOT

    digest = hashlib.sha1(f"{source}|{bbox}|{start.isoformat()}|{end.isoformat()}".encode()).hexdigest()[:16]
    return ROOT / "data" / "local" / "firms_cache" / f"firms_{digest}.json"


def filter_by_acquired_window(
    observations: list[ThermalObservation],
    start: date,
    end: date,
) -> list[ThermalObservation]:
    out: list[ThermalObservation] = []
    for obs in observations:
        day = obs.acquired_at.astimezone(timezone.utc).date()
        if start <= day <= end:
            out.append(obs)
    return out


def _dedup_observations(rows: list[ThermalObservation]) -> list[ThermalObservation]:
    seen: set[tuple] = set()
    unique: list[ThermalObservation] = []
    for obs in rows:
        key = (round(obs.latitude, 4), round(obs.longitude, 4), obs.acquired_at.isoformat(), obs.satellite, obs.frp)
        if key in seen:
            continue
        seen.add(key)
        unique.append(obs)
    unique.sort(key=lambda o: (o.acquired_at, o.id))
    return unique


def parse_firms_csv(
    text: str,
    source: str = "firms",
    provenance_extra: dict[str, Any] | None = None,
) -> list[ThermalObservation]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = [h.strip().lower() for h in lines[0].split(",")]
    required = {"latitude", "longitude"}
    if not required.issubset(set(header)):
        raise ValueError("FIRMS CSV missing required latitude/longitude columns")
    extra = provenance_extra or {}
    rows: list[ThermalObservation] = []
    for index, line in enumerate(lines[1:], start=1):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(header):
            continue
        raw = dict(zip(header, parts, strict=False))
        lat = raw.get("latitude")
        lon = raw.get("longitude")
        if not lat or not lon:
            continue
        acq_date = raw.get("acq_date") or raw.get("acqdate")
        acq_time = (raw.get("acq_time") or raw.get("acqtime") or "0000").zfill(4)
        if not acq_date:
            continue
        hour, minute = int(acq_time[:2]), int(acq_time[2:4])
        acquired = datetime.fromisoformat(acq_date).replace(hour=hour, minute=minute, tzinfo=timezone.utc)
        brightness = raw.get("bright_ti4") or raw.get("brightness") or raw.get("bright_t31")
        mode = extra.get("mode", "live")
        obs_id = f"FIRMS-{mode}-{acq_date}-{acq_time}-{index}"
        provenance = {"provider": extra.get("provider") or "FirmsDataProvider", "row": index, **extra}
        rows.append(
            parse_observation(
                {
                    "id": obs_id,
                    "latitude": lat,
                    "longitude": lon,
                    "acquired_at": acquired.isoformat(),
                    "brightness": brightness or None,
                    "frp": raw.get("frp") or None,
                    "confidence": raw.get("confidence") or None,
                    "sensor": raw.get("instrument") or raw.get("sensor"),
                    "satellite": raw.get("satellite"),
                    "day_night": raw.get("daynight") or raw.get("day_night"),
                    "scan": raw.get("scan") or None,
                    "track": raw.get("track") or None,
                    "source_dataset": raw.get("version") or extra.get("firms_source") or "FIRMS",
                    "observation_quality": None,
                    "provenance": provenance,
                },
                source=source,
            )
        )
    return rows


class OSMContextProvider(ContextProvider):
    name = "OSMContextProvider"
    mode = "LIVE OSM / OVERPASS"

    def __init__(self) -> None:
        settings = get_settings()
        self.overpass_url = settings.overpass_url
        self.timeout_s = float(settings.overpass_timeout_seconds)
        self.batch_size = max(1, int(settings.overpass_batch_size))
        self.ttl_s = int(settings.context_cache_ttl_seconds)
        self.inter_batch_sleep_s = float(settings.overpass_inter_batch_sleep_s)
        self.query_count = 0
        self.last_error: str | None = None
        self._cache: dict[str, tuple[float, list[IndustrialFacility] | None]] = {}

    def land_context(self, lat: float, lon: float) -> tuple[str | None, str, list[str]]:
        return None, "unknown", []

    def facilities_near(self, lat: float, lon: float, radius_m: float = 4000) -> list[IndustrialFacility] | None:
        key = _osm_cell_key(lat, lon, radius_m)
        cached = self._get_cached(key)
        if cached is not _CACHE_MISS:
            return cached
        fetched = self.prefetch_cells([(round(lat, 2), round(lon, 2))], radius_m)
        return fetched.get(key)

    def prefetch_cells(self, cells: list[tuple[float, float]], radius_m: float) -> dict[str, list[IndustrialFacility] | None]:
        """One Overpass bbox request per nearby group of cluster cells — never per observation."""
        import time
        from collections import defaultdict

        from app.context.enrichment import cell_key

        results: dict[str, list[IndustrialFacility] | None] = {}
        pending: list[tuple[str, float, float]] = []
        for lat, lon in cells:
            key = cell_key(lat, lon, radius_m)
            cached = self._get_cached(key)
            if cached is not _CACHE_MISS:
                results[key] = cached
            else:
                pending.append((key, lat, lon))
        groups: dict[tuple[float, float], list[tuple[str, float, float]]] = defaultdict(list)
        for item in pending:
            _key, lat, lon = item
            groups[(round(lat), round(lon))].append(item)
        group_list = list(groups.values())
        for idx, group in enumerate(group_list):
            if idx and self.inter_batch_sleep_s:
                time.sleep(self.inter_batch_sleep_s)
            parsed = self._query_group([(lat, lon) for _k, lat, lon in group], radius_m)
            now = datetime.now(timezone.utc).timestamp()
            if parsed is None:
                for key, _lat, _lon in group:
                    self._cache[key] = (now, None)
                    results[key] = None
                if self.last_error == "overpass rate limited":
                    for later in group_list[idx + 1 :]:
                        for key, _lat, _lon in later:
                            self._cache[key] = (now, None)
                            results[key] = None
                    break
                continue
            for key, lat, lon in group:
                nearby = [
                    fac
                    for fac in parsed
                    if haversine_m(lat, lon, fac.latitude, fac.longitude) <= radius_m + 1200
                ]
                self._cache[key] = (now, nearby)
                results[key] = nearby
        return results

    def _get_cached(self, key: str) -> list[IndustrialFacility] | None | object:
        row = self._cache.get(key)
        if row is None:
            return _CACHE_MISS
        stored_at, value = row
        if datetime.now(timezone.utc).timestamp() - stored_at > self.ttl_s:
            return _CACHE_MISS
        return value

    def _query_group(self, points: list[tuple[float, float]], radius_m: float) -> list[IndustrialFacility] | None:
        timeout = max(5, int(self.timeout_s))
        pad = (radius_m + 500.0) / 111320.0
        south = min(p[0] for p in points) - pad
        north = max(p[0] for p in points) + pad
        west = min(p[1] for p in points) - pad
        east = max(p[1] for p in points) + pad
        bbox = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
        query = (
            f"[out:json][timeout:{timeout}];("
            f'way["landuse"="industrial"]({bbox});'
            f'node["landuse"="industrial"]({bbox});'
            f'way["industrial"]({bbox});'
            f'node["industrial"]({bbox});'
            f'way["man_made"="works"]({bbox});'
            f'node["man_made"="works"]({bbox});'
            f'way["power"="plant"]({bbox});'
            f'node["power"="plant"]({bbox});'
            f");out center tags;"
        )
        payload = self._post_overpass(query)
        if payload is None:
            return None
        elements = payload.get("elements")
        if not isinstance(elements, list):
            self.last_error = "malformed Overpass response"
            return None
        return _dedup_facilities([fac for fac in (_parse_osm_element(el) for el in elements) if fac is not None])

    def _post_overpass(self, query: str) -> dict[str, Any] | None:
        headers = {
            "User-Agent": "thermal-intelligence/0.1 (SIH26162 student prototype; OSM context enrichment)",
            "Accept": "application/json",
        }
        self.query_count += 1
        try:
            response = httpx.post(
                self.overpass_url,
                data={"data": query},
                timeout=self.timeout_s + 15.0,
                headers=headers,
            )
        except httpx.TimeoutException:
            self.last_error = "overpass timeout"
            return None
        except httpx.HTTPError as exc:
            self.last_error = f"overpass request failed: {exc.__class__.__name__}"
            return None
        if response.status_code == 429:
            self.last_error = "overpass rate limited"
            return None
        if response.is_error:
            self.last_error = f"overpass HTTP {response.status_code}"
            return None
        try:
            payload = response.json()
        except ValueError:
            self.last_error = "malformed Overpass response"
            return None
        if not isinstance(payload, dict):
            self.last_error = "malformed Overpass response"
            return None
        self.last_error = None
        return payload


_CACHE_MISS = object()


def _osm_cell_key(lat: float, lon: float, radius_m: float) -> str:
    from app.context.enrichment import cell_key

    return cell_key(lat, lon, radius_m)


def _parse_osm_element(element: Any) -> IndustrialFacility | None:
    if not isinstance(element, dict):
        return None
    tags = element.get("tags") or {}
    if not isinstance(tags, dict):
        tags = {}
    if "lat" in element and "lon" in element:
        elat, elon = element["lat"], element["lon"]
    else:
        center = element.get("center") or {}
        if not isinstance(center, dict) or "lat" not in center or "lon" not in center:
            return None
        elat, elon = center["lat"], center["lon"]
    try:
        lat_f, lon_f = float(elat), float(elon)
    except (TypeError, ValueError):
        return None
    fid = str(element.get("id") or "")
    if not fid:
        return None
    osm_class = tags.get("industrial") or tags.get("landuse") or tags.get("man_made") or tags.get("power")
    return IndustrialFacility(
        id=f"OSM-{element.get('type', 'n')}-{fid}",
        name=tags.get("name") or tags.get("industrial") or "OSM industrial feature",
        facility_type=osm_class,
        latitude=lat_f,
        longitude=lon_f,
        osm_id=fid,
        source="osm",
        provenance={"provider": "OSMContextProvider", "osm_class": osm_class, "spatial_association_only": True},
    )


def _dedup_facilities(facilities: list[IndustrialFacility]) -> list[IndustrialFacility]:
    unique: list[IndustrialFacility] = []
    seen_ids: set[str] = set()
    for fac in facilities:
        if fac.id in seen_ids:
            continue
        if any(haversine_m(fac.latitude, fac.longitude, u.latitude, u.longitude) < 80 for u in unique):
            continue
        seen_ids.add(fac.id)
        unique.append(fac)
    return unique
