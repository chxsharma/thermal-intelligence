from __future__ import annotations

from datetime import datetime

from app.clustering.engine import cluster_summary, count_since, intensity_trend
from app.geo import day_night_norm, haversine_m, parse_confidence
from app.schemas.domain import FeatureVector, IndustrialFacility, ThermalObservation

FEATURE_SCHEMA_VERSION = "features-1.1"


def _context_for_cluster(
    lat: float,
    lon: float,
    facilities: list[IndustrialFacility] | None,
    context_status: str,
    land_context: str | None,
    osm_types: list[str],
) -> dict:
    if facilities is None:
        return {
            "nearest_industrial_distance": None,
            "industrial_count_1km": None,
            "industrial_count_2km": None,
            "context_status": "not_available",
            "context_completeness": 0.2,
            "land_context": land_context,
            "osm_object_types": osm_types,
        }
    if not facilities:
        completeness = 0.55 if context_status in {"available", "not_found"} else 0.25
        status = context_status if context_status != "available" else "not_found"
        return {
            "nearest_industrial_distance": None,
            "industrial_count_1km": 0 if status == "not_found" else None,
            "industrial_count_2km": 0 if status == "not_found" else None,
            "context_status": status,
            "context_completeness": completeness,
            "land_context": land_context,
            "osm_object_types": osm_types,
        }
    distances = [haversine_m(lat, lon, f.latitude, f.longitude) for f in facilities]
    nearest = min(distances)
    return {
        "nearest_industrial_distance": nearest,
        "industrial_count_1km": sum(1 for d in distances if d <= 1000),
        "industrial_count_2km": sum(1 for d in distances if d <= 2000),
        "context_status": "available",
        "context_completeness": 0.9 if land_context else 0.7,
        "land_context": land_context,
        "osm_object_types": osm_types,
    }


def build_feature_vector(
    cluster_id: str,
    observations: list[ThermalObservation],
    facilities: list[IndustrialFacility] | None,
    *,
    as_of: datetime | None = None,
    land_context: str | None = None,
    osm_types: list[str] | None = None,
    context_status: str = "available",
) -> FeatureVector:
    summary = cluster_summary(cluster_id, observations, as_of=as_of)
    visible = [o for o in observations if o.acquired_at <= (as_of or summary["last_seen"])]
    if not visible:
        visible = observations
    confidences = [parse_confidence(o.confidence) for o in visible]
    confidences_present = [c for c in confidences if c is not None]
    days = [day_night_norm(o.day_night) for o in visible]
    night_count = sum(1 for d in days if d == "N")
    day_count = sum(1 for d in days if d == "D")
    dominant_dn = None
    if night_count or day_count:
        dominant_dn = "N" if night_count >= day_count else "D"
    ctx = _context_for_cluster(
        summary["centroid_lat"],
        summary["centroid_lon"],
        facilities,
        context_status,
        land_context,
        osm_types or [],
    )
    span_days = max(1, (summary["last_seen"] - summary["first_seen"]).days + 1)
    density = summary["observation_count"] / span_days
    frps = [o.frp for o in visible if o.frp is not None]
    brights = [o.brightness for o in visible if o.brightness is not None]
    end = as_of or summary["last_seen"]
    duration_s = (summary["last_seen"] - summary["first_seen"]).total_seconds()
    duration_h = max(0.0, duration_s / 3600.0)
    duration_d = duration_h / 24.0
    historical = duration_h >= 14 * 24
    window_note = None if historical else "Historical persistence unavailable for current live window."
    return FeatureVector(
        cluster_id=cluster_id,
        brightness=(sum(brights) / len(brights)) if brights else None,
        frp=(sum(frps) / len(frps)) if frps else None,
        confidence=(sum(confidences_present) / len(confidences_present)) if confidences_present else None,
        day_night=dominant_dn,
        observation_count=summary["observation_count"],
        detections_7d=count_since(visible, end, 7),
        detections_14d=count_since(visible, end, 14),
        detections_30d=count_since(visible, end, 30),
        detections_90d=count_since(visible, end, 90),
        active_days=summary["active_days"],
        spatial_stability=summary["spatial_stability"],
        nearest_industrial_distance=ctx["nearest_industrial_distance"],
        industrial_count_1km=ctx["industrial_count_1km"],
        industrial_count_2km=ctx["industrial_count_2km"],
        land_context=ctx["land_context"],
        source_density=density,
        context_completeness=ctx["context_completeness"],
        context_status=ctx["context_status"],
        night_count=night_count,
        day_count=day_count,
        intensity_trend=intensity_trend(visible),
        missing_frp=len(frps) == 0,
        missing_confidence=len(confidences_present) == 0,
        osm_object_types=ctx["osm_object_types"],
        observed_duration_hours=round(duration_h, 4),
        observed_duration_days=round(duration_d, 4),
        detections_in_window=summary["observation_count"],
        historical_persistence_available=historical,
        window_note=window_note,
    )
