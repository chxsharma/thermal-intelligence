from datetime import datetime, timedelta, timezone

from app.classification.engine import (
    EvidenceBaselineClassifier,
    LABEL_ABNORMAL,
    LABEL_AGRICULTURE,
    LABEL_INSUFFICIENT,
    LABEL_PERSISTENT,
    LABEL_VEGETATION,
)
from app.clustering.engine import cluster_observations
from app.features.engineering import build_feature_vector
from app.schemas.domain import FeatureVector, IndustrialFacility, ThermalObservation


def obs(**kwargs) -> ThermalObservation:
    base = dict(
        id="o1",
        latitude=22.37,
        longitude=69.86,
        acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        brightness=340,
        frp=20,
        confidence="n",
        sensor="VIIRS",
        satellite="NOAA-20",
        day_night="N",
        source_dataset="test",
        source="test",
    )
    base.update(kwargs)
    return ThermalObservation(**base)


def test_repeated_observations_form_one_cluster():
    records = [
        obs(id=f"r{i}", acquired_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(hours=i * 12), latitude=22.370 + i * 0.0002)
        for i in range(8)
    ]
    grouped = cluster_observations(records)
    assert len(grouped) == 1


def test_same_location_same_day_same_cluster():
    records = [
        obs(id="a1", acquired_at=datetime(2026, 9, 1, 2, tzinfo=timezone.utc)),
        obs(id="a2", acquired_at=datetime(2026, 9, 1, 14, tzinfo=timezone.utc)),
    ]
    grouped = cluster_observations(records)
    assert len(grouped) == 1


def test_same_location_beyond_temporal_gap_separate_clusters():
    records = [
        obs(id="b1", acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        obs(id="b2", acquired_at=datetime(2026, 9, 4, tzinfo=timezone.utc)),
    ]
    grouped = cluster_observations(records, temporal_gap_hours=48)
    assert len(grouped) == 2


def test_nearby_short_gap_same_cluster():
    records = [
        obs(id="c1", latitude=22.370, longitude=69.860, acquired_at=datetime(2026, 9, 1, 0, tzinfo=timezone.utc)),
        obs(id="c2", latitude=22.374, longitude=69.860, acquired_at=datetime(2026, 9, 1, 6, tzinfo=timezone.utc)),
    ]
    grouped = cluster_observations(records)
    assert len(grouped) == 1


def test_nearby_long_gap_separate_clusters():
    records = [
        obs(id="d1", latitude=22.370, longitude=69.860, acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        obs(id="d2", latitude=22.374, longitude=69.860, acquired_at=datetime(2026, 9, 5, tzinfo=timezone.utc)),
    ]
    grouped = cluster_observations(records, temporal_gap_hours=48)
    assert len(grouped) == 2


def test_far_apart_same_time_separate_clusters():
    records = [
        obs(id="e1", latitude=22.370, longitude=69.860, acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        obs(id="e2", latitude=22.390, longitude=69.860, acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
    ]
    grouped = cluster_observations(records)
    assert len(grouped) == 2


def test_industrial_site_small_drift_not_split():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    records = [
        obs(id="f0", latitude=22.3700, longitude=69.8600, acquired_at=t0),
        obs(id="f1", latitude=22.3725, longitude=69.8615, acquired_at=t0 + timedelta(hours=6)),
        obs(id="f2", latitude=22.3688, longitude=69.8586, acquired_at=t0 + timedelta(hours=12)),
        obs(id="f3", latitude=22.3738, longitude=69.8579, acquired_at=t0 + timedelta(hours=18)),
        obs(id="f4", latitude=22.3672, longitude=69.8624, acquired_at=t0 + timedelta(hours=24)),
    ]
    grouped = cluster_observations(records)
    assert len(grouped) == 1


def test_centroid_walk_does_not_chain_unrelated_hotspots():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    records = [
        obs(
            id=f"g{i}",
            latitude=22.370 + i * 0.0072,
            longitude=69.860,
            acquired_at=t0 + timedelta(hours=i),
        )
        for i in range(8)
    ]
    grouped = cluster_observations(records)
    assert len(grouped) > 1
    by_id = {o.id: o.cluster_id for members in grouped.values() for o in members}
    assert by_id["g0"] != by_id["g7"]


def test_clustering_is_deterministic():
    records = [
        obs(id="z2", latitude=22.371, acquired_at=datetime(2026, 9, 1, 3, tzinfo=timezone.utc)),
        obs(id="z1", latitude=22.370, acquired_at=datetime(2026, 9, 1, 1, tzinfo=timezone.utc)),
        obs(id="z3", latitude=10.0, longitude=10.0, acquired_at=datetime(2026, 9, 1, 2, tzinfo=timezone.utc)),
    ]
    first = cluster_observations([obs(**r.model_dump()) for r in records])
    second = cluster_observations([obs(**r.model_dump()) for r in records])
    assert set(first) == set(second)
    assert {cid: [o.id for o in members] for cid, members in first.items()} == {
        cid: [o.id for o in members] for cid, members in second.items()
    }


def test_single_observation_is_own_cluster():
    grouped = cluster_observations([obs()])
    assert len(grouped) == 1
    assert list(grouped.values())[0][0].id == "o1"


def test_clustering_diagnostics_match_group_sizes():
    from app.clustering.engine import clustering_diagnostics

    near = [
        obs(id="n1", acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        obs(id="n2", acquired_at=datetime(2026, 9, 2, tzinfo=timezone.utc), latitude=22.371),
    ]
    far = obs(id="f1", latitude=10.0, longitude=10.0, acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    grouped = cluster_observations(near + [far])
    stats = clustering_diagnostics(grouped)
    assert stats["observation_count"] == 3
    assert stats["cluster_count"] == 2
    assert stats["single_observation_cluster_count"] == 1
    assert stats["multi_day_cluster_count"] == 1
    assert stats["largest_cluster_size"] == 2
    assert stats["spatial_threshold_m"] == 1000.0
    assert stats["temporal_gap_hours"] == 48.0
    assert stats["temporal_split"] is True
    assert "median_cluster_duration_hours" in stats


def test_missing_frp_and_confidence_features():
    vector = build_feature_vector("c1", [obs(frp=None, confidence=None)], [], context_status="not_available")
    assert vector.missing_frp is True
    assert vector.missing_confidence is True
    assert vector.frp is None
    assert vector.confidence is None


def test_no_industrial_context_is_not_treated_as_zero_facilities():
    vector = build_feature_vector("c1", [obs()], None, context_status="not_available")
    assert vector.industrial_count_1km is None
    assert vector.nearest_industrial_distance is None
    assert vector.context_status == "not_available"


def test_osm_not_found_is_explicit():
    vector = build_feature_vector("c1", [obs()], [], context_status="not_found", land_context="forest / wildland vegetation")
    assert vector.context_status == "not_found"
    assert vector.industrial_count_1km == 0


def test_persistent_industrial_not_accident():
    facility = IndustrialFacility(id="f", name="refinery", latitude=22.371, longitude=69.8605, source="test")
    records = [
        obs(id=f"p{i}", acquired_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(days=i * 2), day_night="N")
        for i in range(20)
    ]
    features = build_feature_vector("c1", records, [facility], land_context="industrial / refinery complex", context_status="available")
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_PERSISTENT
    assert result.label != LABEL_ABNORMAL


def test_uncertain_case_insufficient_evidence():
    features = FeatureVector(
        cluster_id="u",
        observation_count=1,
        detections_7d=1,
        active_days=1,
        context_status="not_available",
        context_completeness=0.2,
        missing_frp=True,
        missing_confidence=True,
    )
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_INSUFFICIENT
    assert result.confidence_band == "UNRESOLVED"


def test_conflicting_evidence_does_not_invent_cause():
    facility = IndustrialFacility(id="f", name="estate", latitude=18.627, longitude=73.805, source="test")
    records = [
        obs(id=f"x{i}", latitude=18.629, longitude=73.801, acquired_at=datetime(2026, 9, 9, tzinfo=timezone.utc) + timedelta(hours=8 * i), frp=15)
        for i in range(6)
    ]
    features = build_feature_vector(
        "c1",
        records,
        [facility],
        land_context="mixed industrial / vegetation fringe",
        context_status="available",
    )
    result = EvidenceBaselineClassifier().classify(features)
    assert "this facility caused" not in json_blob(result)
    assert result.why_not["industrial_source"]


def test_vegetation_without_industry():
    records = [
        obs(
            id=f"v{i}",
            latitude=29.39 + i * 0.004,
            longitude=79.45 + i * 0.003,
            acquired_at=datetime(2026, 9, 8, tzinfo=timezone.utc) + timedelta(hours=6 * i),
        )
        for i in range(10)
    ]
    features = build_feature_vector("c1", records, [], land_context="forest / wildland vegetation", context_status="not_found")
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label in {LABEL_VEGETATION, LABEL_INSUFFICIENT}


def test_agricultural_day_crop():
    records = [
        obs(
            id=f"a{i}",
            latitude=30.90 + (i % 3) * 0.002,
            longitude=75.85,
            acquired_at=datetime(2026, 9, 11, tzinfo=timezone.utc) + timedelta(hours=5 * i),
            day_night="D",
            frp=7,
        )
        for i in range(8)
    ]
    features = build_feature_vector("c1", records, [], land_context="cropland / agricultural", context_status="not_found")
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label in {LABEL_AGRICULTURE, LABEL_VEGETATION, LABEL_INSUFFICIENT}


def json_blob(result) -> str:
    return result.model_dump_json().lower()
