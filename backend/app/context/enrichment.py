from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.geo import haversine_m
from app.schemas.domain import IndustrialFacility


class ContextSource(Protocol):
    name: str

    def facilities_near(self, lat: float, lon: float, radius_m: float = 4000) -> list[IndustrialFacility] | None: ...

    def land_context(self, lat: float, lon: float) -> tuple[str | None, str, list[str]]: ...

    def prefetch_cells(self, cells: list[tuple[float, float]], radius_m: float) -> dict[str, list[IndustrialFacility] | None]: ...


def cell_key(lat: float, lon: float, radius_m: float) -> str:
    return f"{round(lat, 2):.2f}:{round(lon, 2):.2f}:{int(radius_m)}"


@dataclass
class ClusterContext:
    """OSM/demo supporting context for one thermal source cluster.

    This is not ground truth and does not assert that a facility caused a detection.
    """

    facilities: list[IndustrialFacility] | None
    nearest: IndustrialFacility | None
    nearest_distance_m: float | None
    industrial_count_1km: int | None
    industrial_count_2km: int | None
    osm_object_types: list[str]
    land_context: str | None
    context_status: str
    context_completeness: float
    cache_hit: bool
    provider_error: str | None = None


@dataclass
class ContextStats:
    overpass_queries: int = 0
    cache_hits: int = 0
    fallback_used: bool = False
    last_error: str | None = None
    cluster_statuses: dict[str, str] = field(default_factory=dict)


class ContextEnrichmentProvider:
    """ThermalCluster → context enrichment → OSM/Overpass (or in-memory demo context).

    Live FIRMS does not fall back to demo facilities. Overpass failure is not_available.
    Queries are issued per cache cell of cluster centroids, never per raw observation.
    """

    name = "ContextEnrichmentProvider"
    search_radius_m = 4000.0

    def __init__(self, primary: ContextSource, fallback: ContextSource | None = None) -> None:
        self.primary = primary
        self.fallback = fallback
        self.stats = ContextStats()
        self._cell_cache: dict[str, list[IndustrialFacility] | None] = {}
        self._cluster_cache: dict[str, ClusterContext] = {}
        self._scope_ids: set[str] | None = None

    def set_scope(self, cluster_ids: set[str] | None) -> None:
        """If set, only these cluster IDs may trigger Overpass. Others stay unknown."""
        self._scope_ids = cluster_ids

    def prefetch(self, clusters: list[tuple[str, float, float]]) -> None:
        """Load Overpass context for unique centroid cells. One request per batch of cells."""
        if self._scope_ids is not None:
            clusters = [c for c in clusters if c[0] in self._scope_ids]
        if not clusters:
            return
        needed: dict[str, tuple[float, float]] = {}
        for _cid, lat, lon in clusters:
            key = cell_key(lat, lon, self.search_radius_m)
            if key not in self._cell_cache:
                needed[key] = (round(lat, 2), round(lon, 2))
        if not needed:
            return
        prefetch = getattr(self.primary, "prefetch_cells", None)
        if callable(prefetch):
            fetched = prefetch(list(needed.values()), self.search_radius_m)
            for key, center in needed.items():
                cell = cell_key(center[0], center[1], self.search_radius_m)
                self._cell_cache[cell] = fetched.get(cell, fetched.get(key))
        else:
            for key, center in needed.items():
                self._cell_cache[key] = self.primary.facilities_near(center[0], center[1], self.search_radius_m)

    def enrich(self, cluster_id: str, lat: float, lon: float) -> ClusterContext:
        cached = self._cluster_cache.get(cluster_id)
        if cached is not None:
            self.stats.cache_hits += 1
            self.stats.cluster_statuses[cluster_id] = cached.context_status
            return cached
        if self._scope_ids is not None and cluster_id not in self._scope_ids:
            ctx = ClusterContext(
                facilities=None,
                nearest=None,
                nearest_distance_m=None,
                industrial_count_1km=None,
                industrial_count_2km=None,
                osm_object_types=[],
                land_context=None,
                context_status="unknown",
                context_completeness=0.2,
                cache_hit=False,
                provider_error=None,
            )
            self._cluster_cache[cluster_id] = ctx
            self.stats.cluster_statuses[cluster_id] = ctx.context_status
            return ctx
        key = cell_key(lat, lon, self.search_radius_m)
        facilities: list[IndustrialFacility] | None
        error: str | None = None
        if key in self._cell_cache:
            self.stats.cache_hits += 1
            facilities = self._cell_cache[key]
        else:
            facilities = self.primary.facilities_near(lat, lon, self.search_radius_m)
            self._cell_cache[key] = facilities
        if facilities is None:
            error = getattr(self.primary, "last_error", None) or "context provider unavailable"
            self.stats.last_error = error
            ctx = self._unavailable(error, cache_hit=True)
        else:
            ctx = self._from_facilities(facilities, lat, lon, cache_hit=True, error=None)
            if not facilities:
                land, _status, types = self._primary_land(lat, lon)
                ctx.land_context = land
                ctx.osm_object_types = types or ctx.osm_object_types
                ctx.context_status = "not_found"
                ctx.industrial_count_1km = 0
                ctx.industrial_count_2km = 0
                ctx.context_completeness = 0.55
        self._cluster_cache[cluster_id] = ctx
        self.stats.cluster_statuses[cluster_id] = ctx.context_status
        return ctx

    def map_facilities(self) -> list[IndustrialFacility]:
        """Unique nearest mapped facilities for display; not a complete industrial census."""
        seen: set[str] = set()
        out: list[IndustrialFacility] = []
        for ctx in self._cluster_cache.values():
            if ctx.nearest is None:
                continue
            if ctx.nearest.id in seen:
                continue
            seen.add(ctx.nearest.id)
            out.append(ctx.nearest)
        return out

    def diagnostics(self) -> dict:
        statuses = list(self.stats.cluster_statuses.values())
        available = sum(1 for s in statuses if s == "available")
        not_found = sum(1 for s in statuses if s == "not_found")
        not_available = sum(1 for s in statuses if s == "not_available")
        unknown = sum(1 for s in statuses if s == "unknown")
        return {
            "provider": getattr(self.primary, "name", self.name),
            "fallback_provider": getattr(self.fallback, "name", None) if self.fallback else None,
            "fallback_used": self.stats.fallback_used,
            "clusters_enriched": len(statuses),
            "clusters_with_industrial_context": available,
            "clusters_not_found": not_found,
            "clusters_not_available": not_available,
            "clusters_unknown": unknown,
            "overpass_queries": getattr(self.primary, "query_count", self.stats.overpass_queries),
            "cache_hits": self.stats.cache_hits,
            "last_error": self.stats.last_error,
            "note": "OSM is supporting context, not ground truth. not_found does not mean no facility exists. Nearby does not mean caused.",
        }

    def _primary_land(self, lat: float, lon: float) -> tuple[str | None, str, list[str]]:
        land_fn = getattr(self.primary, "land_context", None)
        if callable(land_fn):
            return land_fn(lat, lon)
        return None, "unknown", []

    def _unavailable(self, error: str | None, cache_hit: bool) -> ClusterContext:
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
            cache_hit=cache_hit,
            provider_error=error,
        )

    def _from_facilities(
        self,
        facilities: list[IndustrialFacility],
        lat: float,
        lon: float,
        cache_hit: bool,
        error: str | None,
    ) -> ClusterContext:
        nearby = [f for f in facilities if haversine_m(lat, lon, f.latitude, f.longitude) <= self.search_radius_m]
        if not nearby:
            return ClusterContext(
                facilities=[],
                nearest=None,
                nearest_distance_m=None,
                industrial_count_1km=0,
                industrial_count_2km=0,
                osm_object_types=[],
                land_context=None,
                context_status="not_found",
                context_completeness=0.55,
                cache_hit=cache_hit,
                provider_error=error,
            )
        distances = [(haversine_m(lat, lon, f.latitude, f.longitude), f) for f in nearby]
        distances.sort(key=lambda item: (item[0], item[1].id))
        nearest_d, nearest = distances[0]
        types = _collect_types(nearby)
        return ClusterContext(
            facilities=nearby,
            nearest=nearest,
            nearest_distance_m=nearest_d,
            industrial_count_1km=sum(1 for d, _f in distances if d <= 1000),
            industrial_count_2km=sum(1 for d, _f in distances if d <= 2000),
            osm_object_types=types,
            land_context="OSM-mapped industrial / man-made features" if types else "mapped industrial features",
            context_status="available",
            context_completeness=0.7 if types else 0.65,
            cache_hit=cache_hit,
            provider_error=error,
        )


def _collect_types(facilities: list[IndustrialFacility]) -> list[str]:
    types: list[str] = []
    seen: set[str] = set()
    for fac in facilities:
        label = fac.facility_type or fac.provenance.get("osm_class")
        if not label or label in seen:
            continue
        seen.add(label)
        types.append(str(label))
    return types
