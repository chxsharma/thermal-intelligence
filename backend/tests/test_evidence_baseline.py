from datetime import datetime, timedelta, timezone

from app.classification.engine import (
    LABEL_ABNORMAL,
    LABEL_AGRICULTURE,
    LABEL_INSUFFICIENT,
    LABEL_OTHER,
    LABEL_PERSISTENT,
    LABEL_VEGETATION,
    EvidenceBaselineClassifier,
    get_classifier,
)
from app.features.engineering import build_feature_vector
from app.schemas.domain import FeatureVector, IndustrialFacility, ThermalObservation


def _obs(**kwargs) -> ThermalObservation:
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


def _facility() -> IndustrialFacility:
    return IndustrialFacility(id="f", name="refinery", latitude=22.371, longitude=69.8605, source="test")


def test_strong_industrial_context_abnormal_event():
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    records = [
        _obs(id=f"a{i}", acquired_at=t0 + timedelta(hours=4 * i), frp=18 + i * 8, day_night="N")
        for i in range(5)
    ]
    features = build_feature_vector(
        "c1",
        records,
        [_facility()],
        land_context="industrial / refinery complex",
        context_status="available",
    )
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_ABNORMAL
    assert result.classifier_name == "Evidence Baseline"
    dist = next(e for e in result.supporting_evidence if e.feature == "industrial_facility_distance")
    assert dist.effect
    assert dist.actual_value
    assert "caused" not in (dist.explanation.lower()) or "not causation" in dist.explanation.lower()


def test_persistent_source_with_industrial_context():
    facility = _facility()
    records = [
        _obs(id=f"p{i}", acquired_at=datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(days=i * 2), day_night="N")
        for i in range(20)
    ]
    features = build_feature_vector(
        "c1", records, [facility], land_context="industrial / refinery complex", context_status="available"
    )
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_PERSISTENT
    assert result.label != LABEL_ABNORMAL
    assert features.historical_persistence_available is True


def test_vegetation_style_source():
    records = [
        _obs(
            id=f"v{i}",
            latitude=29.39 + i * 0.004,
            longitude=79.45 + i * 0.003,
            acquired_at=datetime(2026, 9, 8, tzinfo=timezone.utc) + timedelta(hours=6 * i),
            frp=12,
        )
        for i in range(10)
    ]
    features = build_feature_vector("c1", records, [], land_context="forest / wildland vegetation", context_status="not_found")
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_VEGETATION
    assert result.label not in {LABEL_PERSISTENT, LABEL_ABNORMAL}


def test_agricultural_style_source():
    records = [
        _obs(
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
    assert result.label == LABEL_AGRICULTURE


def test_missing_osm_not_found_is_not_no_industry():
    records = [_obs(id=f"n{i}", acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(hours=i)) for i in range(4)]
    features = build_feature_vector("c1", records, [], context_status="not_found")
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label not in {LABEL_PERSISTENT, LABEL_ABNORMAL}
    text = result.model_dump_json().lower()
    assert "not_found" in text
    assert "no facility exists" in text


def test_osm_unavailable_does_not_invent_industry():
    records = [_obs(id=f"u{i}", acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(hours=3 * i), frp=22) for i in range(4)]
    features = build_feature_vector("c1", records, None, context_status="not_available")
    result = EvidenceBaselineClassifier().classify(features)
    assert features.industrial_count_1km is None
    assert result.label not in {LABEL_PERSISTENT, LABEL_ABNORMAL}
    assert any(e.feature == "context_status" and e.actual_value == "not_available" for e in result.counter_evidence)


def test_weak_insufficient_evidence():
    features = FeatureVector(
        cluster_id="u",
        observation_count=1,
        detections_in_window=1,
        active_days=1,
        context_status="not_available",
        context_completeness=0.2,
        missing_frp=True,
        missing_confidence=True,
        observed_duration_hours=0,
        historical_persistence_available=False,
        window_note="Historical persistence unavailable for current live window.",
    )
    result = EvidenceBaselineClassifier().classify(features)
    assert result.label == LABEL_INSUFFICIENT
    assert result.confidence_band == "UNRESOLVED"


def test_conflicting_evidence_does_not_force_cause():
    facility = IndustrialFacility(id="f", name="estate", latitude=18.627, longitude=73.805, source="test")
    records = [
        _obs(id=f"x{i}", latitude=18.629, longitude=73.801, acquired_at=datetime(2026, 9, 9, tzinfo=timezone.utc) + timedelta(hours=8 * i), frp=15)
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
    blob = result.model_dump_json().lower()
    assert "this facility caused" not in blob
    assert result.label in {LABEL_OTHER, LABEL_INSUFFICIENT, LABEL_ABNORMAL}
    assert any(e.code == "conflict" for e in result.counter_evidence) or "different directions" in result.why_not["industrial_source"].lower()


def test_short_observation_duration_is_counter_evidence():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    records = [
        _obs(id="s1", acquired_at=t0, frp=30),
        _obs(id="s2", acquired_at=t0 + timedelta(hours=3), frp=32),
    ]
    features = build_feature_vector("c1", records, [_facility()], land_context="industrial / refinery complex", context_status="available")
    result = EvidenceBaselineClassifier().classify(features)
    assert features.observed_duration_hours < 24
    assert any(e.code == "short_duration" for e in result.counter_evidence)
    assert result.label != LABEL_PERSISTENT


def test_classification_is_deterministic():
    records = [_obs(id=f"d{i}", acquired_at=datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(hours=i), frp=10) for i in range(3)]
    features = build_feature_vector("c1", records, None, context_status="not_available")
    clf = EvidenceBaselineClassifier()
    first = clf.classify(features)
    second = clf.classify(features)
    assert first.model_dump() == second.model_dump()
    assert get_classifier().name == "Evidence Baseline"
