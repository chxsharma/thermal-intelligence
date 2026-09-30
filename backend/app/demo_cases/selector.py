"""Deterministic SIH live-demo case selection.

Does not add HTTP APIs, change clustering, or change Evidence Baseline rules.
OSM lookups are capped; missing context is never invented.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.classification.engine import LABEL_INSUFFICIENT, EvidenceBaselineClassifier
from app.clustering.engine import cluster_observations, cluster_summary
from app.context.enrichment import ClusterContext, ContextEnrichmentProvider
from app.context.sample import select_geographically_distributed_clusters
from app.features.engineering import build_feature_vector
from app.geo import haversine_m
from app.schemas.domain import ThermalObservation

SELECTOR_VERSION = "live-demo-cases-1.0"
MAX_DEMO_CASES = 3
MAX_OSM_LOOKUPS = 3
DEFAULT_BBOX_PAD_DEG = 0.20


def _obs_key(obs: ThermalObservation) -> tuple:
    return (
        round(obs.latitude, 4),
        round(obs.longitude, 4),
        obs.acquired_at.isoformat(),
        obs.satellite,
        obs.frp,
    )


def associate_historical(
    clusters: dict[str, list[ThermalObservation]],
    historical: list[ThermalObservation],
    radius_m: float,
) -> dict[str, list[ThermalObservation]]:
    """Spatially associate archive rows to existing live clusters. Does not recluster."""
    assigned: dict[str, list[ThermalObservation]] = {cid: [] for cid in clusters}
    if not historical or not clusters:
        return assigned
    centroids: list[tuple[str, float, float]] = []
    live_keys: dict[str, set[tuple]] = {}
    for cid, members in clusters.items():
        summary = cluster_summary(cid, members)
        centroids.append((cid, summary["centroid_lat"], summary["centroid_lon"]))
        live_keys[cid] = {_obs_key(o) for o in members}
    for obs in historical:
        best_id = None
        best_d = None
        for cid, lat, lon in centroids:
            dist = haversine_m(obs.latitude, obs.longitude, lat, lon)
            if dist > radius_m:
                continue
            if best_id is None or dist < best_d or (dist == best_d and cid < best_id):
                best_d = dist
                best_id = cid
        if best_id is None:
            continue
        if _obs_key(obs) in live_keys[best_id]:
            continue
        assigned[best_id].append(obs)
        live_keys[best_id].add(_obs_key(obs))
    for cid in assigned:
        assigned[cid].sort(key=lambda o: (o.acquired_at, o.id))
    return assigned


def modest_bbox(lat: float, lon: float, pad_deg: float = DEFAULT_BBOX_PAD_DEG) -> str:
    return f"{lon - pad_deg:.4f},{lat - pad_deg:.4f},{lon + pad_deg:.4f},{lat + pad_deg:.4f}"


def _pre_rank_key(row: dict[str, Any]) -> tuple:
    return (
        -int(row["live_observation_count"]),
        -int(row["historical_observation_count"]),
        -int(row["live_active_days"]),
        -float(row["spatial_stability"] if row["spatial_stability"] is not None else -1.0),
        round(float(row["latitude"]), 6),
        round(float(row["longitude"]), 6),
        str(row["cluster_id"]),
    )


def _final_rank_key(row: dict[str, Any]) -> tuple:
    meets = 0 if row["classification"] == LABEL_INSUFFICIENT else 1
    osm_ok = 1 if row["osm_context_status"] == "available" else 0
    near = 1 if row.get("nearest_facility_m") is not None and row["nearest_facility_m"] <= 1000 else 0
    return (
        -meets,
        -osm_ok,
        -near,
        -int(row["observation_count"]),
        -int(row["historical_observation_count"]),
        str(row["cluster_id"]),
    )


def _evidence_rows(items: list[Any]) -> list[dict[str, str]]:
    out = []
    for item in items:
        out.append(
            {
                "code": item.code,
                "feature": item.feature,
                "actual_value": item.actual_value,
                "effect": item.effect,
                "explanation": item.explanation,
            }
        )
    return out


def _empty_context() -> ClusterContext:
    return ClusterContext(
        facilities=None,
        nearest=None,
        nearest_distance_m=None,
        industrial_count_1km=None,
        industrial_count_2km=None,
        osm_object_types=[],
        land_context=None,
        context_status="not_available",
        context_completeness=0.2,
        cache_hit=False,
        provider_error="OSM not queried for this cluster",
    )


def _enrich_top(
    ranked_ids: list[str],
    centroids: dict[str, tuple[float, float]],
    osm_provider: Any,
    max_osm: int,
) -> dict[str, ClusterContext]:
    chosen = ranked_ids[: max(0, int(max_osm))]
    if not chosen or osm_provider is None:
        return {}
    enrichment = ContextEnrichmentProvider(primary=osm_provider, fallback=None)
    enrichment.set_scope(set(chosen))
    sample = [(cid, centroids[cid][0], centroids[cid][1]) for cid in chosen]
    enrichment.prefetch(sample)
    out: dict[str, ClusterContext] = {}
    for cid, lat, lon in sample:
        out[cid] = enrichment.enrich(cid, lat, lon)
    return out


def score_demo_candidates(
    live_observations: list[ThermalObservation],
    historical_observations: list[ThermalObservation] | None = None,
    *,
    contexts: dict[str, ClusterContext] | None = None,
    osm_provider: Any | None = None,
    max_osm: int = MAX_OSM_LOOKUPS,
    spatial_radius_m: float = 1000.0,
    temporal_gap_hours: float = 48.0,
    as_of: datetime | None = None,
    osm_query_hook: Callable[[list[tuple[str, float, float]]], None] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    grouped = cluster_observations(
        live_observations,
        spatial_threshold_m=spatial_radius_m,
        temporal_gap_hours=temporal_gap_hours,
    )
    historical = historical_observations or []
    hist_by_cluster = associate_historical(grouped, historical, spatial_radius_m)
    moment = as_of or max((o.acquired_at for o in live_observations), default=datetime.now(timezone.utc))
    pre_rows: list[dict[str, Any]] = []
    centroids: dict[str, tuple[float, float]] = {}
    for cid, members in grouped.items():
        summary = cluster_summary(cid, members, as_of=moment)
        centroids[cid] = (summary["centroid_lat"], summary["centroid_lon"])
        pre_rows.append(
            {
                "cluster_id": cid,
                "latitude": summary["centroid_lat"],
                "longitude": summary["centroid_lon"],
                "live_observation_count": summary["observation_count"],
                "historical_observation_count": len(hist_by_cluster.get(cid, [])),
                "live_active_days": summary["active_days"],
                "spatial_stability": summary["spatial_stability"],
            }
        )
    pre_rows.sort(key=_pre_rank_key)
    ranked_ids = [row["cluster_id"] for row in pre_rows]

    resolved: dict[str, ClusterContext] = dict(contexts or {})
    need_osm = [cid for cid in ranked_ids if cid not in resolved]
    osm_ids: list[str] = []
    if osm_provider is not None and need_osm:
        pool = need_osm[:20]
        spread = select_geographically_distributed_clusters(
            [(cid, centroids[cid][0], centroids[cid][1]) for cid in pool],
            limit=max_osm,
        )
        spread_ids = [cid for cid, _lat, _lon in spread]
        fetched = _enrich_top(spread_ids, centroids, osm_provider, max_osm)
        resolved.update(fetched)
        osm_ids = list(fetched.keys())
        if osm_query_hook is not None:
            osm_query_hook([(cid, centroids[cid][0], centroids[cid][1]) for cid in fetched])

    classifier = EvidenceBaselineClassifier()
    built: list[dict[str, Any]] = []
    for cid in ranked_ids:
        live_members = grouped[cid]
        hist_members = hist_by_cluster.get(cid, [])
        combined = live_members + hist_members
        ctx = resolved.get(cid) or _empty_context()
        features = build_feature_vector(
            cid,
            combined,
            ctx.facilities,
            as_of=moment,
            land_context=ctx.land_context,
            osm_types=ctx.osm_object_types,
            context_status=ctx.context_status,
        )
        classification = classifier.classify(features)
        summary = cluster_summary(cid, combined, as_of=moment)
        nearest = None
        if ctx.nearest is not None:
            nearest = {
                "id": ctx.nearest.id,
                "name": ctx.nearest.name,
                "facility_type": ctx.nearest.facility_type,
                "latitude": ctx.nearest.latitude,
                "longitude": ctx.nearest.longitude,
                "distance_m": ctx.nearest_distance_m,
            }
        live_times = [o.acquired_at for o in live_members]
        built.append(
            {
                "cluster_id": cid,
                "latitude": summary["centroid_lat"],
                "longitude": summary["centroid_lon"],
                "observation_count": summary["observation_count"],
                "live_observation_count": len(live_members),
                "historical_observation_count": len(hist_members),
                "observation_date_range": {
                    "start": min(o.acquired_at for o in combined).isoformat(),
                    "end": max(o.acquired_at for o in combined).isoformat(),
                },
                "live_date_range": {
                    "start": min(live_times).isoformat(),
                    "end": max(live_times).isoformat(),
                },
                "osm_context_status": ctx.context_status,
                "nearest_industrial_facility": nearest,
                "nearest_facility_m": ctx.nearest_distance_m,
                "classification": classification.label,
                "confidence_band": classification.confidence_band,
                "priority": classification.priority,
                "supporting_evidence": _evidence_rows(classification.supporting_evidence),
                "counter_evidence": _evidence_rows(classification.counter_evidence),
                "spatial_stability": summary["spatial_stability"],
                "frp_mean": summary["intensity_statistics"]["frp_mean"],
                "active_days": summary["active_days"],
                "historical_persistence_available": features.historical_persistence_available,
                "selector_version": SELECTOR_VERSION,
            }
        )

    built.sort(key=_final_rank_key)
    return built, osm_ids, pre_rows


def select_demo_cases(
    live_observations: list[ThermalObservation],
    historical_observations: list[ThermalObservation] | None = None,
    *,
    contexts: dict[str, ClusterContext] | None = None,
    osm_provider: Any | None = None,
    max_cases: int = MAX_DEMO_CASES,
    max_osm: int = MAX_OSM_LOOKUPS,
    spatial_radius_m: float = 1000.0,
    temporal_gap_hours: float = 48.0,
    as_of: datetime | None = None,
    osm_query_hook: Callable[[list[tuple[str, float, float]]], None] | None = None,
) -> list[dict[str, Any]]:
    """Return up to `max_cases` reproducible live demo clusters.

    Same observation inputs always produce the same ordered IDs.
    Clusters that remain Insufficient Evidence are not manufactured into other labels.
    """
    scored, _osm_ids, _pre = score_demo_candidates(
        live_observations,
        historical_observations,
        contexts=contexts,
        osm_provider=osm_provider,
        max_osm=max_osm,
        spatial_radius_m=spatial_radius_m,
        temporal_gap_hours=temporal_gap_hours,
        as_of=as_of,
        osm_query_hook=osm_query_hook,
    )
    return [row for row in scored if row["classification"] != LABEL_INSUFFICIENT][: max(0, int(max_cases))]


def historical_bboxes_for_candidates(
    cases_or_pre: list[dict[str, Any]],
    *,
    limit: int = MAX_OSM_LOOKUPS,
    pad_deg: float = DEFAULT_BBOX_PAD_DEG,
) -> list[str]:
    """One modest bbox per top candidate; merge identical rounded boxes."""
    boxes: list[str] = []
    seen: set[str] = set()
    for row in cases_or_pre[:limit]:
        box = modest_bbox(float(row["latitude"]), float(row["longitude"]), pad_deg)
        if box in seen:
            continue
        seen.add(box)
        boxes.append(box)
    return boxes


def prepare_live_demo_cases(*, max_cases: int = MAX_DEMO_CASES, max_osm: int = MAX_OSM_LOOKUPS) -> dict[str, Any]:
    """One-shot live selection using existing FIRMS/OSM providers. Not an HTTP API."""
    from app.clustering.engine import cluster_observations as _cluster
    from app.config import get_settings
    from app.providers.live import HistoricalFIRMSProvider, LiveFIRMSProvider, OSMContextProvider

    settings = get_settings()
    live = LiveFIRMSProvider().fetch_observations()
    grouped = _cluster(
        live,
        spatial_threshold_m=settings.cluster_spatial_radius_m,
        temporal_gap_hours=settings.cluster_temporal_gap_hours,
    )
    pre = []
    for cid, members in grouped.items():
        summary = cluster_summary(cid, members)
        pre.append(
            {
                "cluster_id": cid,
                "latitude": summary["centroid_lat"],
                "longitude": summary["centroid_lon"],
                "live_observation_count": summary["observation_count"],
                "historical_observation_count": 0,
                "live_active_days": summary["active_days"],
                "spatial_stability": summary["spatial_stability"],
            }
        )
    pre.sort(key=_pre_rank_key)
    pool = pre[:20]
    spread = select_geographically_distributed_clusters(
        [(row["cluster_id"], row["latitude"], row["longitude"]) for row in pool],
        limit=max_osm,
    )
    spread_pre = []
    by_id = {row["cluster_id"]: row for row in pre}
    for cid, _lat, _lon in spread:
        spread_pre.append(by_id[cid])
    boxes = historical_bboxes_for_candidates(spread_pre, limit=max_osm)
    hist_provider = HistoricalFIRMSProvider()
    historical: list[ThermalObservation] = []
    hist_reports: list[dict[str, Any]] = []
    for box in boxes:
        rows = hist_provider.fetch_historical(
            days=30,
            bbox=box,
            source="VIIRS_SNPP_NRT",
            use_cache=True,
            chunk_sleep_s=1.0,
            exclude_live_nrt_window=True,
        )
        historical.extend(rows)
        report = dict(hist_provider.last_historical_report or {})
        report.pop("cache_path", None)
        hist_reports.append(report)

    osm = OSMContextProvider()
    scored, osm_ids, _pre_after = score_demo_candidates(
        live,
        historical,
        osm_provider=osm,
        max_osm=max_osm,
        spatial_radius_m=settings.cluster_spatial_radius_m,
        temporal_gap_hours=settings.cluster_temporal_gap_hours,
    )
    selected = [row for row in scored if row["classification"] != LABEL_INSUFFICIENT][:max_cases]
    osm_evaluated = [row for row in scored if row["cluster_id"] in set(osm_ids)]
    return {
        "selector_version": SELECTOR_VERSION,
        "live_observation_count": len(live),
        "live_cluster_count": len(grouped),
        "historical_observation_count": len(historical),
        "historical_bboxes": boxes,
        "historical_reports": hist_reports,
        "osm_queries": osm.query_count,
        "osm_cluster_ids": osm_ids,
        "osm_evaluated": osm_evaluated,
        "selected": selected,
    }

