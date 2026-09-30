from __future__ import annotations

import time
from typing import Any

from app.clustering.engine import cluster_observations, cluster_summary
from app.context.enrichment import ContextEnrichmentProvider
from app.context.sample import select_geographically_distributed_clusters
from app.providers.live import OSMContextProvider
from app.schemas.domain import ThermalObservation


def run_osm_cluster_validation(
    observations: list[ThermalObservation],
    *,
    limit: int = 10,
    spatial_threshold_m: float = 1000.0,
    temporal_gap_hours: float = 48.0,
    inter_batch_sleep_s: float = 8.0,
    osm: OSMContextProvider | None = None,
) -> dict[str, Any]:
    """Enrich exactly `limit` geographically spread clusters. Never more."""
    started = time.perf_counter()
    grouped = cluster_observations(
        observations,
        spatial_threshold_m=spatial_threshold_m,
        temporal_gap_hours=temporal_gap_hours,
    )
    as_of = max((o.acquired_at for o in observations), default=None)
    centroids: list[tuple[str, float, float]] = []
    for cluster_id, members in grouped.items():
        summary = cluster_summary(cluster_id, members, as_of=as_of)
        centroids.append((cluster_id, summary["centroid_lat"], summary["centroid_lon"]))
    sample = select_geographically_distributed_clusters(centroids, limit)
    provider = osm or OSMContextProvider()
    provider.inter_batch_sleep_s = inter_batch_sleep_s
    enrichment = ContextEnrichmentProvider(primary=provider, fallback=None)
    enrichment.set_scope({cid for cid, _lat, _lon in sample})
    enrichment.prefetch(sample)
    errors: list[str] = []
    industrial_feature_ids: set[str] = set()
    for cid, lat, lon in sample:
        ctx = enrichment.enrich(cid, lat, lon)
        if ctx.provider_error:
            errors.append(f"{cid}: {ctx.provider_error}")
        if ctx.facilities:
            for fac in ctx.facilities:
                industrial_feature_ids.add(fac.id)
    elapsed_s = round(time.perf_counter() - started, 3)
    statuses = [enrichment._cluster_cache[cid].context_status for cid, _a, _b in sample]
    unique_errors = sorted(set(errors))
    return {
        "clusters_attempted": len(sample),
        "successful_osm_queries": sum(1 for s in statuses if s in {"available", "not_found"}),
        "clusters_with_industrial_context": sum(1 for s in statuses if s == "available"),
        "clusters_with_no_mapped_context": sum(1 for s in statuses if s == "not_found"),
        "clusters_not_available": sum(1 for s in statuses if s == "not_available"),
        "industrial_features_found": len(industrial_feature_ids),
        "runtime_seconds": elapsed_s,
        "errors": unique_errors,
        "sample_cluster_ids": [cid for cid, _a, _b in sample],
        "overpass_queries": provider.query_count,
        "last_error": provider.last_error,
    }
