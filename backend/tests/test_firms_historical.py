from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.providers.live import (
    FirmsDataProvider,
    HistoricalFIRMSProvider,
    LiveFIRMSProvider,
    clip_archive_window,
    filter_by_acquired_window,
    historical_chunk_windows,
    parse_data_availability,
    parse_firms_csv,
    processing_label_for_source,
    resolve_archive_window,
)


CSV = """latitude,longitude,acq_date,acq_time,frp,confidence,bright_ti4,daynight,satellite,instrument,version
22.37,69.86,2026-08-01,1812,12.5,n,340.1,N,N,VIIRS,2.0NRT
22.38,69.87,2026-08-20,0910,8.1,h,330.0,D,N,VIIRS,2.0NRT
"""

AVAIL_NRT = """data_id,min_date,max_date
VIIRS_SNPP_NRT,2026-03-01,2026-09-14
"""

AVAIL_SP = """data_id,min_date,max_date
VIIRS_SNPP_SP,2012-01-20,2026-04-27
"""


def _hist_settings(**kwargs):
    base = dict(
        firms_map_key="k",
        firms_source="VIIRS_SNPP_NRT",
        firms_days=5,
        firms_historical_source="VIIRS_SNPP_NRT",
        firms_historical_days=30,
        firms_historical_bbox="69.80,22.30,70.00,22.45",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_historical_parse_and_provenance():
    rows = parse_firms_csv(
        CSV,
        provenance_extra={
            "provider": "HistoricalFIRMSProvider",
            "mode": "historical",
            "firms_source": "VIIRS_SNPP_NRT",
            "processing": "nrt_archive",
            "ingested_at": "2026-09-14T00:00:00+00:00",
        },
    )
    assert len(rows) == 2
    assert rows[0].source == "firms"
    assert rows[0].sensor == "VIIRS"
    assert rows[0].provenance["mode"] == "historical"
    assert rows[0].provenance["provider"] == "HistoricalFIRMSProvider"
    assert rows[0].provenance["processing"] == "nrt_archive"
    assert rows[0].provenance["ingested_at"]
    assert rows[0].acquired_at == datetime(2026, 8, 1, 18, 12, tzinfo=timezone.utc)


def test_date_window_filtering():
    rows = parse_firms_csv(CSV, provenance_extra={"mode": "historical"})
    kept = filter_by_acquired_window(rows, date(2026, 8, 15), date(2026, 8, 31))
    assert len(kept) == 1
    assert kept[0].acquired_at.date() == date(2026, 8, 20)


def test_historical_chunk_windows_cover_30_days():
    windows = historical_chunk_windows(date(2026, 8, 16), date(2026, 9, 14), 5)
    assert sum(span for _start, span in windows) == 30
    assert all(span <= 5 for _start, span in windows)


def test_empty_historical_csv():
    assert parse_firms_csv("") == []


def test_parse_availability_and_clip():
    assert parse_data_availability(AVAIL_NRT, "VIIRS_SNPP_NRT") == (date(2026, 3, 1), date(2026, 9, 14))
    assert parse_data_availability(AVAIL_SP, "VIIRS_SNPP_SP") == (date(2012, 1, 20), date(2026, 4, 27))
    assert parse_data_availability("Invalid date", "VIIRS_SNPP_NRT") is None
    start, end = clip_archive_window(
        date(2026, 8, 16),
        date(2026, 9, 14),
        date(2012, 1, 20),
        date(2026, 4, 27),
        today=date(2026, 9, 14),
        live_days=5,
        exclude_live_nrt_window=True,
    )
    assert start is None and end is None
    start, end = clip_archive_window(
        date(2026, 8, 16),
        date(2026, 9, 14),
        date(2026, 3, 1),
        date(2026, 9, 14),
        today=date(2026, 9, 14),
        live_days=5,
        exclude_live_nrt_window=True,
    )
    assert start == date(2026, 8, 16)
    assert end == date(2026, 9, 9)
    start, end = resolve_archive_window(
        date(2026, 8, 16),
        date(2026, 9, 14),
        date(2026, 4, 28),
        date(2026, 9, 14),
        today=date(2026, 9, 14),
        live_days=5,
        window_days=30,
        end_date_explicit=False,
        exclude_live_nrt_window=True,
    )
    assert start == date(2026, 8, 11)
    assert end == date(2026, 9, 9)
    assert (end - start).days + 1 == 30
    assert processing_label_for_source("VIIRS_SNPP_NRT") == "nrt_archive"
    assert processing_label_for_source("VIIRS_SNPP_SP") == "standard_quality"


def test_historical_empty_http_body(monkeypatch, tmp_path):
    monkeypatch.setattr("app.providers.live.get_settings", lambda: _hist_settings())
    monkeypatch.setattr("app.providers.live.historical_cache_path", lambda *a, **k: tmp_path / "h.json")

    class Resp:
        is_error = False
        text = "Invalid date"

    monkeypatch.setattr("app.providers.live.httpx.get", lambda *a, **k: Resp())
    provider = FirmsDataProvider()
    rows = provider.fetch_historical(days=5, end_date=date(2026, 8, 5), chunk_sleep_s=0, use_cache=False)
    assert rows == []
    assert provider.last_historical_report["record_count"] == 0
    assert provider.last_historical_report["area_http"] == 0


def test_historical_cache_reuse(monkeypatch, tmp_path):
    monkeypatch.setattr("app.providers.live.get_settings", lambda: _hist_settings())
    cache = tmp_path / "h.json"
    monkeypatch.setattr("app.providers.live.historical_cache_path", lambda *a, **k: cache)
    calls = {"n": 0, "avail": 0, "area": 0}

    class Resp:
        is_error = False

        def __init__(self, text):
            self.text = text

    def fake_get(url, timeout=None):
        calls["n"] += 1
        if "data_availability" in url:
            calls["avail"] += 1
            return Resp(AVAIL_NRT)
        calls["area"] += 1
        assert "VIIRS_SNPP_NRT" in url
        assert url.rstrip("/").split("/")[-1].startswith("2026-")
        return Resp(CSV)

    monkeypatch.setattr("app.providers.live.httpx.get", fake_get)
    provider = HistoricalFIRMSProvider()
    first = provider.fetch_historical(days=5, end_date=date(2026, 8, 20), chunk_sleep_s=0, use_cache=True)
    assert first
    assert first[0].provenance["processing"] == "nrt_archive"
    area_after_first = calls["area"]
    assert calls["avail"] == 1
    assert area_after_first >= 1
    second = provider.fetch_historical(days=5, end_date=date(2026, 8, 20), chunk_sleep_s=0, use_cache=True)
    assert len(second) == len(first)
    assert calls["area"] == area_after_first
    assert provider.last_historical_report["cache_hit"] is True


def test_historical_does_not_query_outside_sp_availability(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.providers.live.get_settings",
        lambda: _hist_settings(firms_historical_source="VIIRS_SNPP_SP"),
    )
    monkeypatch.setattr("app.providers.live.historical_cache_path", lambda *a, **k: tmp_path / "h.json")
    area_calls = {"n": 0}

    class Resp:
        is_error = False
        text = AVAIL_SP

    def fake_get(url, timeout=None):
        if "data_availability" in url:
            return Resp()
        area_calls["n"] += 1
        return Resp()

    monkeypatch.setattr("app.providers.live.httpx.get", fake_get)
    rows = HistoricalFIRMSProvider().fetch_historical(
        days=30,
        end_date=date(2026, 9, 14),
        source="VIIRS_SNPP_SP",
        chunk_sleep_s=0,
        use_cache=False,
    )
    assert rows == []
    assert area_calls["n"] == 0


def test_live_nrt_url_unaffected(monkeypatch):
    settings = SimpleNamespace(
        firms_map_key="k",
        firms_source="VIIRS_SNPP_NRT",
        firms_days=5,
        firms_bbox="68.0,8.0,97.5,37.5",
    )
    monkeypatch.setattr("app.providers.live.get_settings", lambda: settings)
    seen = {}

    class Resp:
        is_error = False
        text = CSV

    def fake_get(url, timeout=None):
        seen["url"] = url
        return Resp()

    monkeypatch.setattr("app.providers.live.httpx.get", fake_get)
    rows = LiveFIRMSProvider().fetch_observations()
    assert rows
    assert "VIIRS_SNPP_NRT" in seen["url"]
    assert seen["url"].rstrip("/").split("/")[-1] == "5"
    assert "data_availability" not in seen["url"]
    assert rows[0].provenance["mode"] == "live"
    assert rows[0].provenance["processing"] == "nrt_current"
    assert "/2026-" not in seen["url"]
    pipeline_rows = FirmsDataProvider().fetch_observations()
    assert pipeline_rows
    assert FirmsDataProvider().name == "FirmsDataProvider"
