import httpx

from app.context.enrichment import ContextEnrichmentProvider
from app.providers.live import OSMContextProvider


def _osm(monkeypatch) -> OSMContextProvider:
    provider = OSMContextProvider()
    provider.inter_batch_sleep_s = 0
    return provider


def _cluster_ctx(provider: OSMContextProvider, points: list[tuple[str, float, float]]) -> ContextEnrichmentProvider:
    enrichment = ContextEnrichmentProvider(primary=provider, fallback=None)
    enrichment.prefetch(points)
    return enrichment


def test_industrial_facility_found_nearby(monkeypatch):
    lat, lon = 22.370, 69.860

    def fake_post(*args, **kwargs):
        return _json_response(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 101,
                        "lat": lat + 0.001,
                        "lon": lon + 0.001,
                        "tags": {"name": "Test works", "industrial": "refinery"},
                    }
                ]
            }
        )

    monkeypatch.setattr("app.providers.live.httpx.post", fake_post)
    osm = _osm(monkeypatch)
    enrichment = _cluster_ctx(osm, [("c1", lat, lon)])
    ctx = enrichment.enrich("c1", lat, lon)
    assert ctx.context_status == "available"
    assert ctx.nearest is not None
    assert ctx.nearest.name == "Test works"
    assert ctx.nearest_distance_m is not None and ctx.nearest_distance_m < 1000
    assert ctx.industrial_count_1km == 1
    assert "refinery" in ctx.osm_object_types


def test_no_facility_found(monkeypatch):
    monkeypatch.setattr("app.providers.live.httpx.post", lambda *a, **k: _json_response({"elements": []}))
    osm = _osm(monkeypatch)
    enrichment = _cluster_ctx(osm, [("c1", 26.91, 71.00)])
    ctx = enrichment.enrich("c1", 26.91, 71.00)
    assert ctx.context_status == "not_found"
    assert ctx.facilities == []
    assert ctx.industrial_count_1km == 0
    assert ctx.industrial_count_2km == 0
    assert ctx.nearest is None


def test_multiple_facilities_nearby(monkeypatch):
    lat, lon = 17.6924, 83.2210

    def fake_post(*args, **kwargs):
        return _json_response(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": lat + 0.002,
                        "lon": lon,
                        "tags": {"name": "Plant A", "landuse": "industrial"},
                    },
                    {
                        "type": "way",
                        "id": 2,
                        "center": {"lat": lat + 0.012, "lon": lon},
                        "tags": {"name": "Plant B", "man_made": "works"},
                    },
                    {
                        "type": "node",
                        "id": 3,
                        "lat": lat + 0.03,
                        "lon": lon,
                        "tags": {"name": "Too far", "landuse": "industrial"},
                    },
                ]
            }
        )

    monkeypatch.setattr("app.providers.live.httpx.post", fake_post)
    osm = _osm(monkeypatch)
    enrichment = _cluster_ctx(osm, [("c1", lat, lon)])
    ctx = enrichment.enrich("c1", lat, lon)
    assert ctx.context_status == "available"
    assert ctx.industrial_count_1km == 1
    assert ctx.industrial_count_2km == 2
    assert ctx.nearest is not None and ctx.nearest.name == "Plant A"


def test_provider_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.providers.live.httpx.post", boom)
    osm = _osm(monkeypatch)
    enrichment = _cluster_ctx(osm, [("c1", 22.37, 69.86)])
    ctx = enrichment.enrich("c1", 22.37, 69.86)
    assert ctx.context_status == "not_available"
    assert ctx.facilities is None
    assert ctx.industrial_count_1km is None
    assert ctx.provider_error == "overpass timeout"


def test_repeated_query_uses_cached_context(monkeypatch):
    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _json_response({"elements": []})

    monkeypatch.setattr("app.providers.live.httpx.post", fake_post)
    osm = _osm(monkeypatch)
    enrichment = ContextEnrichmentProvider(primary=osm, fallback=None)
    points = [("c1", 22.370, 69.860), ("c2", 22.371, 69.861)]
    enrichment.prefetch(points)
    first = enrichment.enrich("c1", 22.370, 69.860)
    second = enrichment.enrich("c1", 22.370, 69.860)
    nearby = enrichment.enrich("c2", 22.371, 69.861)
    assert calls["n"] == 1
    assert osm.query_count == 1
    assert first.context_status == "not_found"
    assert second.cache_hit is True
    assert nearby.context_status == "not_found"


def test_rate_limited_overpass_is_not_available(monkeypatch):
    class Limited:
        status_code = 429
        is_error = True

        def json(self):
            raise ValueError("no body")

    monkeypatch.setattr("app.providers.live.httpx.post", lambda *a, **k: Limited())
    osm = _osm(monkeypatch)
    enrichment = _cluster_ctx(osm, [("c1", 22.37, 69.86)])
    ctx = enrichment.enrich("c1", 22.37, 69.86)
    assert ctx.context_status == "not_available"
    assert ctx.facilities is None
    assert osm.last_error == "overpass rate limited"


def test_overpass_failure_is_not_available_not_not_found(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.providers.live.httpx.post", boom)
    osm = _osm(monkeypatch)
    enrichment = ContextEnrichmentProvider(primary=osm, fallback=None)
    enrichment.prefetch([("c1", 22.370, 69.860)])
    ctx = enrichment.enrich("c1", 22.370, 69.860)
    assert ctx.context_status == "not_available"
    assert ctx.facilities is None
    assert ctx.industrial_count_1km is None


def test_validation_scope_does_not_query_other_clusters(monkeypatch):
    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _json_response({"elements": []})

    monkeypatch.setattr("app.providers.live.httpx.post", fake_post)
    osm = _osm(monkeypatch)
    enrichment = ContextEnrichmentProvider(primary=osm, fallback=None)
    enrichment.set_scope({"keep"})
    enrichment.prefetch([("keep", 22.370, 69.860), ("skip", 28.600, 77.200)])
    keep = enrichment.enrich("keep", 22.370, 69.860)
    skip = enrichment.enrich("skip", 28.600, 77.200)
    assert calls["n"] == 1
    assert keep.context_status == "not_found"
    assert skip.context_status == "unknown"


def test_validation_runs_at_most_ten_clusters(monkeypatch):
    from datetime import datetime, timezone

    from app.context.validate import run_osm_cluster_validation
    from app.schemas.domain import ThermalObservation

    calls = {"n": 0}

    def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _json_response({"elements": []})

    monkeypatch.setattr("app.providers.live.httpx.post", fake_post)
    osm = _osm(monkeypatch)
    records = [
        ThermalObservation(
            id=f"o{i}",
            latitude=8.0 + i * 2.0,
            longitude=70.0 + i * 1.5,
            acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            source="firms",
        )
        for i in range(15)
    ]
    report = run_osm_cluster_validation(records, limit=10, inter_batch_sleep_s=0, osm=osm)
    assert report["clusters_attempted"] == 10
    assert len(report["sample_cluster_ids"]) == 10
    assert calls["n"] <= 10
    assert calls["n"] >= 1


def test_osm_sample_pins_demo_case_without_raising_limit():
    from app.context.sample import sample_live_osm_clusters

    clusters = [(f"c{i}", 8.0 + i * 2.5, 70.0 + (i % 4) * 6.0) for i in range(20)]
    clusters.append(("SRC-A4964848", 28.05, 69.37))
    sample = sample_live_osm_clusters(clusters, 10, ["SRC-A4964848"])
    assert len(sample) == 10
    assert sample[0][0] == "SRC-A4964848"
    assert len({c[0] for c in sample}) == 10


def test_geographic_sample_is_deterministic_and_size_limited():
    from app.context.sample import select_geographically_distributed_clusters

    clusters = [
        (f"c{i}", 8.0 + i * 2.5, 70.0 + (i % 4) * 6.0)
        for i in range(20)
    ]
    first = select_geographically_distributed_clusters(clusters, 10)
    second = select_geographically_distributed_clusters(clusters, 10)
    assert len(first) == 10
    assert first == second
    ids = {c[0] for c in first}
    assert len(ids) == 10


class _JsonResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.is_error = False

    def json(self):
        return self._payload


def _json_response(payload):
    return _JsonResponse(payload)
