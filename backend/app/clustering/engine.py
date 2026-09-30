from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.geo import haversine_m, mean_point, median_point, unique_days
from app.schemas.domain import ThermalObservation

SPATIAL_THRESHOLD_M = 1000.0
TEMPORAL_GAP_HOURS = 48.0


def cluster_observations(
    observations: list[ThermalObservation],
    spatial_threshold_m: float = SPATIAL_THRESHOLD_M,
    temporal_gap_hours: float = TEMPORAL_GAP_HOURS,
) -> dict[str, list[ThermalObservation]]:
    """Deterministic greedy clustering for a thermal source/event.

    This groups raw FIRMS observations into thermal source clusters only.
    It does not decide persistent sources or investigated events.

    Observations are sorted by time, then latitude, then longitude, then id.
    An observation joins the first existing cluster that is both:
    - spatially close to the cluster median AND the cluster anchor (first member)
    - temporally related to the cluster last_seen (gap ≤ temporal_gap_hours)

    Using an anchor plus median avoids walking-centroid chain merges while still
    absorbing small industrial-site drift. Time gaps split clusters.
    """
    ordered = sorted(
        observations,
        key=lambda o: (o.acquired_at, round(o.latitude, 6), round(o.longitude, 6), o.id),
    )
    groups: list[list[ThermalObservation]] = []
    for obs in ordered:
        assigned = False
        for group in groups:
            if _belongs_to_cluster(obs, group, spatial_threshold_m, temporal_gap_hours):
                group.append(obs)
                assigned = True
                break
        if not assigned:
            groups.append([obs])

    clustered: dict[str, list[ThermalObservation]] = {}
    for group in groups:
        seed = min(group, key=lambda o: (o.acquired_at, o.id))
        digest = hashlib.sha1(f"{seed.id}:{round(seed.latitude, 4)}:{round(seed.longitude, 4)}".encode()).hexdigest()[:8]
        cluster_id = f"SRC-{digest.upper()}"
        for member in group:
            member.cluster_id = cluster_id
        clustered[cluster_id] = group
    return clustered


def _belongs_to_cluster(
    obs: ThermalObservation,
    group: list[ThermalObservation],
    spatial_threshold_m: float,
    temporal_gap_hours: float,
) -> bool:
    last_seen = max(o.acquired_at for o in group)
    gap_h = (obs.acquired_at - last_seen).total_seconds() / 3600.0
    if gap_h > temporal_gap_hours:
        return False
    anchor = min(group, key=lambda o: (o.acquired_at, o.id))
    med_lat, med_lon = median_point([(o.latitude, o.longitude) for o in group])
    dist_median = haversine_m(obs.latitude, obs.longitude, med_lat, med_lon)
    dist_anchor = haversine_m(obs.latitude, obs.longitude, anchor.latitude, anchor.longitude)
    return dist_median <= spatial_threshold_m and dist_anchor <= spatial_threshold_m


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def clustering_diagnostics(
    groups: dict[str, list[ThermalObservation]],
    spatial_threshold_m: float = SPATIAL_THRESHOLD_M,
    temporal_gap_hours: float = TEMPORAL_GAP_HOURS,
) -> dict:
    """Counts derived only from the clustered observation set currently in memory."""
    sizes = [len(obs) for obs in groups.values()]
    observation_count = sum(sizes)
    cluster_count = len(groups)
    spans_days: list[float] = []
    spans_hours: list[float] = []
    multi_day = 0
    for obs in groups.values():
        times = [o.acquired_at for o in obs]
        if unique_days(times) > 1:
            multi_day += 1
        span_s = (max(times) - min(times)).total_seconds() if times else 0.0
        spans_days.append(span_s / 86400.0)
        spans_hours.append(span_s / 3600.0)
    return {
        "observation_count": observation_count,
        "cluster_count": cluster_count,
        "average_observations_per_cluster": round(observation_count / cluster_count, 4) if cluster_count else 0.0,
        "largest_cluster_size": max(sizes) if sizes else 0,
        "single_observation_cluster_count": sum(1 for n in sizes if n == 1),
        "multi_day_cluster_count": multi_day,
        "clusters_spanning_7d_plus": sum(1 for d in spans_days if d >= 7),
        "clusters_spanning_14d_plus": sum(1 for d in spans_days if d >= 14),
        "clusters_spanning_30d_plus": sum(1 for d in spans_days if d >= 30),
        "median_cluster_duration_hours": round(_median(spans_hours), 4),
        "spatial_threshold_m": spatial_threshold_m,
        "temporal_gap_hours": temporal_gap_hours,
        "temporal_split": True,
        "note": "Span and duration stats describe clusters in the current observation window only. A 5-day FIRMS pull cannot support 7/14/30-day persistence claims.",
    }


def spatial_stability(observations: list[ThermalObservation]) -> float | None:
    if len(observations) < 2:
        return None
    lat, lon = mean_point([(o.latitude, o.longitude) for o in observations])
    radii = [haversine_m(o.latitude, o.longitude, lat, lon) for o in observations]
    mean_r = sum(radii) / len(radii)
    # 0 = dispersed, 1 = tightly co-located
    return max(0.0, min(1.0, 1.0 - (mean_r / 800.0)))


def count_since(observations: list[ThermalObservation], end: datetime, days: int) -> int:
    start = end - timedelta(days=days)
    return sum(1 for o in observations if start <= o.acquired_at <= end)


def intensity_trend(observations: list[ThermalObservation]) -> str | None:
    vals = [(o.acquired_at, o.frp) for o in observations if o.frp is not None]
    if len(vals) < 3:
        return None
    vals.sort(key=lambda x: x[0])
    mid = len(vals) // 2
    first = sum(v for _, v in vals[:mid]) / mid
    second = sum(v for _, v in vals[mid:]) / (len(vals) - mid)
    if first == 0:
        return "increasing" if second > 0 else "flat"
    change = (second - first) / first
    if change > 0.35:
        return "increasing"
    if change < -0.35:
        return "decreasing"
    return "stable"


def cluster_summary(cluster_id: str, observations: list[ThermalObservation], as_of: datetime | None = None) -> dict:
    times = [o.acquired_at for o in observations]
    end = as_of or max(times)
    visible = [o for o in observations if o.acquired_at <= end]
    if not visible:
        visible = observations
        end = max(times)
    lat, lon = mean_point([(o.latitude, o.longitude) for o in visible])
    frps = [o.frp for o in visible if o.frp is not None]
    brights = [o.brightness for o in visible if o.brightness is not None]
    return {
        "id": cluster_id,
        "centroid_lat": lat,
        "centroid_lon": lon,
        "observation_count": len(visible),
        "active_days": unique_days(o.acquired_at for o in visible),
        "first_seen": min(o.acquired_at for o in visible),
        "last_seen": max(o.acquired_at for o in visible),
        "persistence_7d": count_since(visible, end, 7),
        "persistence_14d": count_since(visible, end, 14),
        "persistence_30d": count_since(visible, end, 30),
        "persistence_90d": count_since(visible, end, 90),
        "spatial_stability": spatial_stability(visible),
        "intensity_statistics": {
            "frp_mean": (sum(frps) / len(frps)) if frps else None,
            "frp_max": max(frps) if frps else None,
            "brightness_mean": (sum(brights) / len(brights)) if brights else None,
        },
    }
