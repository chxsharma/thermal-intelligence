from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ThermalObservation(BaseModel):
    id: str
    latitude: float
    longitude: float
    acquired_at: datetime
    brightness: float | None = None
    frp: float | None = None
    confidence: str | float | None = None
    sensor: str | None = None
    satellite: str | None = None
    day_night: str | None = None
    scan: float | None = None
    track: float | None = None
    source_dataset: str | None = None
    observation_quality: str | None = None
    cluster_id: str | None = None
    source: str = "demo"
    provenance: dict[str, Any] = Field(default_factory=dict)


class IndustrialFacility(BaseModel):
    id: str
    name: str
    facility_type: str | None = None
    latitude: float
    longitude: float
    osm_id: str | None = None
    source: str = "demo"
    provenance: dict[str, Any] = Field(default_factory=dict)


class FeatureVector(BaseModel):
    cluster_id: str
    brightness: float | None = None
    frp: float | None = None
    confidence: float | None = None
    day_night: str | None = None
    observation_count: int = 0
    detections_7d: int = 0
    detections_14d: int = 0
    detections_30d: int = 0
    detections_90d: int = 0
    active_days: int = 0
    spatial_stability: float | None = None
    nearest_industrial_distance: float | None = None
    industrial_count_1km: int | None = None
    industrial_count_2km: int | None = None
    land_context: str | None = None
    source_density: float | None = None
    context_completeness: float | None = None
    context_status: str = "unknown"
    night_count: int = 0
    day_count: int = 0
    intensity_trend: str | None = None
    missing_frp: bool = False
    missing_confidence: bool = False
    osm_object_types: list[str] = Field(default_factory=list)
    observed_duration_hours: float = 0.0
    observed_duration_days: float = 0.0
    detections_in_window: int = 0
    historical_persistence_available: bool = False
    window_note: str | None = None


class EvidenceItem(BaseModel):
    polarity: str
    code: str
    feature: str
    actual_value: str
    effect: str
    explanation: str
    feature_name: str | None = None
    feature_value: str | None = None
    statement: str | None = None


class ClassificationResult(BaseModel):
    cluster_id: str
    label: str
    confidence_band: str
    priority: str
    internal_score: float
    classifier_name: str = "Evidence Baseline"
    classifier_version: str = "evidence-baseline-1.1"
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    counter_evidence: list[EvidenceItem] = Field(default_factory=list)
    why_not: dict[str, str] = Field(default_factory=dict)
    review_recommended: bool = False
    review_reasons: list[str] = Field(default_factory=list)
