from datetime import datetime, timedelta, timezone

from app.classification.engine import LABEL_INSUFFICIENT, LABEL_PERSISTENT
from app.clustering.engine import cluster_observations
from app.context.enrichment import ClusterContext
from app.demo_cases.selector import associate_historical, select_demo_cases
from app.schemas.domain import IndustrialFacility, ThermalObservation


def _obs(oid: str, lat: float, lon: float, when: datetime, **kwargs) -> ThermalObservation:
    payload = dict(
        id=oid,
        latitude=lat,
        longitude=lon,
        acquired_at=when,
        brightness=340,
        frp=22,
        confidence="n",
        sensor="VIIRS",
        satellite="N",
        day_night="N",
        source="firms",
        provenance={"mode": "live"},
    )
    payload.update(kwargs)
    return ThermalObservation(**payload)


def _ctx(name: str, lat: float, lon: float) -> ClusterContext:
    fac = IndustrialFacility(
        id="OSM-n-1",
        name=name,
        facility_type="refinery",
        latitude=lat,
        longitude=lon,
        source="osm",
    )
    return ClusterContext(
        facilities=[fac],
        nearest=fac,
        nearest_distance_m=80.0,
        industrial_count_1km=1,
        industrial_count_2km=1,
        osm_object_types=["refinery"],
        land_context="OSM-mapped industrial / man-made features",
        context_status="available",
        context_completeness=0.7,
        cache_hit=False,
    )


def test_associate_historical_does_not_recluster():
    t0 = datetime(2026, 9, 12, tzinfo=timezone.utc)
    live = [_obs("L1", 22.37, 69.86, t0)]
    grouped = cluster_observations(live)
    hist = [
        _obs("H1", 22.371, 69.861, t0 - timedelta(days=10), provenance={"mode": "historical"}),
        _obs("H2", 28.6, 77.2, t0 - timedelta(days=3), provenance={"mode": "historical"}),
    ]
    assigned = associate_historical(grouped, hist, 1000.0)
    cid = next(iter(grouped))
    assert [o.id for o in assigned[cid]] == ["H1"]
    assert grouped[cid][0].id == "L1"


def test_selector_is_deterministic_and_caps_at_three():
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    live = []
    hist = []
    contexts = {}
    sites = [
        (22.37, 69.86, "Jamnagar works"),
        (21.17, 72.83, "Hazira works"),
        (17.69, 83.22, "Vizag works"),
        (13.08, 80.27, "Chennai works"),
    ]
    for i, (lat, lon, name) in enumerate(sites):
        for d in range(6):
            live.append(_obs(f"L{i}-{d}", lat, lon, t0 + timedelta(days=20 + d)))
        for d in range(12):
            hist.append(_obs(f"H{i}-{d}", lat + 0.0001, lon, t0 + timedelta(days=d * 2)))
        grouped = cluster_observations([o for o in live if abs(o.latitude - lat) < 0.01])
        cid = next(iter(grouped))
        contexts[cid] = _ctx(name, lat, lon)
    first = select_demo_cases(live, hist, contexts=contexts)
    second = select_demo_cases(live, hist, contexts=contexts)
    assert [c["cluster_id"] for c in first] == [c["cluster_id"] for c in second]
    assert len(first) <= 3
    assert all(c["classification"] != LABEL_INSUFFICIENT for c in first)
    assert all(c["historical_observation_count"] > 0 for c in first)
    assert all(c["osm_context_status"] == "available" for c in first)
    assert all(c["nearest_industrial_facility"] is not None for c in first)


def test_selector_returns_fewer_when_evidence_is_weak():
    t0 = datetime(2026, 9, 13, tzinfo=timezone.utc)
    live = [_obs("only", 26.9, 75.8, t0)]
    selected = select_demo_cases(live, [], contexts={})
    assert selected == []


def test_selector_does_not_invent_osm():
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    live = [_obs(f"n{i}", 22.37, 69.86, t0 + timedelta(hours=i)) for i in range(8)]
    selected = select_demo_cases(live, [], contexts={})
    assert selected == []
    grouped = cluster_observations(live)
    cid = next(iter(grouped))
    selected = select_demo_cases(live, [], contexts={cid: _ctx("Jamnagar works", 22.37, 69.86)})
    assert len(selected) == 1
    assert selected[0]["classification"] != LABEL_INSUFFICIENT
    assert selected[0]["nearest_industrial_facility"]["name"] == "Jamnagar works"


class _FakeOSM:
    name = "FakeOSM"

    def land_context(self, lat, lon):
        return None, "unknown", []

    def facilities_near(self, lat, lon, radius_m=4000):
        return []

    def prefetch_cells(self, cells, radius_m):
        from app.context.enrichment import cell_key

        return {cell_key(lat, lon, radius_m): [] for lat, lon in cells}


def test_osm_budget_spreads_across_strong_clusters():
    t0 = datetime(2026, 9, 12, tzinfo=timezone.utc)
    live = []
    sites = [(22.37, 69.86), (28.6, 77.2), (13.08, 80.27), (23.76, 86.40)]
    for i, (lat, lon) in enumerate(sites):
        for n in range(8 - i):
            live.append(_obs(f"s{i}-{n}", lat, lon, t0 + timedelta(hours=n)))
    queried = []
    select_demo_cases(
        live,
        [],
        osm_provider=_FakeOSM(),
        max_osm=3,
        osm_query_hook=lambda rows: queried.extend(rows),
    )
    assert len(queried) == 3
    lats = sorted(round(r[1], 2) for r in queried)
    assert lats[0] != lats[-1]

