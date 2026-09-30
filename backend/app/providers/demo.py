from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.geo import haversine_m
from app.context.enrichment import cell_key
from app.providers.base import ContextProvider, DataProvider, ImageryProvider, parse_observation
from app.schemas.domain import IndustrialFacility, ThermalObservation


@lru_cache
def _context_payload() -> dict[str, Any]:
    path = get_settings().demo_dir / "context.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def _observation_payload() -> list[dict[str, Any]]:
    path = get_settings().demo_dir / "observations.json"
    return json.loads(path.read_text(encoding="utf-8"))


class DemoDataProvider(DataProvider):
    name = "DemoDataProvider"
    mode = "DEMO REPLAY MODE"

    def fetch_observations(self) -> list[ThermalObservation]:
        return [parse_observation(row, "demo") for row in _observation_payload()]


DemoFIRMSProvider = DemoDataProvider


class DemoContextProvider(ContextProvider):
    name = "DemoContextProvider"
    mode = "DEMO REPLAY MODE"

    def __init__(self) -> None:
        payload = _context_payload()
        self.facilities = [IndustrialFacility.model_validate(row) for row in payload["facilities"]]
        self.scenarios = {row["id"]: row for row in payload["scenarios"]}
        self.obs_scenario = {
            row["id"]: row.get("scenario_id") for row in _observation_payload() if "scenario_id" in row
        }

    def all_facilities(self) -> list[IndustrialFacility]:
        return self.facilities

    def scenario_for_cluster_obs(self, observation_ids: list[str]) -> dict[str, Any] | None:
        for oid in observation_ids:
            sid = self.obs_scenario.get(oid)
            if sid and sid in self.scenarios:
                return self.scenarios[sid]
        return None

    def facilities_near(self, lat: float, lon: float, radius_m: float = 4000) -> list[IndustrialFacility] | None:
        found = [f for f in self.facilities if haversine_m(lat, lon, f.latitude, f.longitude) <= radius_m]
        return found

    def prefetch_cells(self, cells: list[tuple[float, float]], radius_m: float) -> dict[str, list[IndustrialFacility] | None]:
        out: dict[str, list[IndustrialFacility] | None] = {}
        for lat, lon in cells:
            out[cell_key(lat, lon, radius_m)] = self.facilities_near(lat, lon, radius_m)
        return out

    def land_context(self, lat: float, lon: float) -> tuple[str | None, str, list[str]]:
        # Match the nearest scenario centroid via facilities / known coords in observations
        best = None
        best_d = 1e12
        for row in _observation_payload():
            d = haversine_m(lat, lon, float(row["latitude"]), float(row["longitude"]))
            if d < best_d:
                best_d = d
                best = row.get("scenario_id")
        if not best or best_d > 15000:
            return None, "unknown", []
        scene = self.scenarios[best]
        return scene.get("land_context"), scene.get("context_status", "unknown"), scene.get("osm_object_types") or []


class DemoImageryProvider(ImageryProvider):
    name = "DemoImageryProvider"
    mode = "DEMO REPLAY MODE"

    def tile_url(self) -> str | None:
        return None
