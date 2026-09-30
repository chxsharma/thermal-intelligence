from __future__ import annotations

from pathlib import Path

from app.geo import haversine_m


def select_geographically_distributed_clusters(
    clusters: list[tuple[str, float, float]],
    limit: int = 10,
) -> list[tuple[str, float, float]]:
    """Deterministic farthest-point sample of cluster centroids.

    Same input always yields the same 10 (or fewer) clusters, spread across
    the geographic extent rather than the first 10 in insertion order.
    """
    if limit <= 0:
        return []
    ordered = sorted(clusters, key=lambda c: (round(c[1], 6), round(c[2], 6), c[0]))
    if len(ordered) <= limit:
        return ordered
    selected = [ordered[0]]
    remaining = ordered[1:]
    while len(selected) < limit and remaining:
        def score(cand: tuple[str, float, float]) -> tuple[float, float, float, str]:
            nearest = min(haversine_m(cand[1], cand[2], s[1], s[2]) for s in selected)
            return (-nearest, cand[1], cand[2], cand[0])

        remaining.sort(key=score)
        selected.append(remaining.pop(0))
    return sorted(selected, key=lambda c: (c[1], c[2], c[0]))


def pinned_live_demo_cluster_ids(path: Path | None = None) -> list[str]:
    """Cluster IDs from the deterministic live demo snapshot, if present."""
    from app.config import ROOT

    target = path or (ROOT / "data" / "demo" / "live_demo_cases.json")
    if not target.exists():
        return []
    import json

    payload = json.loads(target.read_text(encoding="utf-8"))
    ids: list[str] = []
    for row in payload.get("selected") or []:
        cid = row.get("cluster_id")
        if cid and cid not in ids:
            ids.append(cid)
    return ids


def sample_live_osm_clusters(
    clusters: list[tuple[str, float, float]],
    limit: int = 10,
    pinned_ids: list[str] | None = None,
) -> list[tuple[str, float, float]]:
    """Keep OSM within `limit`. Pin known live-demo cases, then geographic fill."""
    if limit <= 0:
        return []
    by_id = {cid: (cid, lat, lon) for cid, lat, lon in clusters}
    pinned: list[tuple[str, float, float]] = []
    for cid in pinned_ids or []:
        if cid in by_id and len(pinned) < limit:
            pinned.append(by_id[cid])
    remainder = [c for c in clusters if c[0] not in {p[0] for p in pinned}]
    geo = select_geographically_distributed_clusters(remainder, max(0, limit - len(pinned)))
    seen = {c[0] for c in pinned}
    out = list(pinned)
    for row in geo:
        if row[0] in seen:
            continue
        out.append(row)
        seen.add(row[0])
        if len(out) >= limit:
            break
    return out
