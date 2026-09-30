from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.schemas.domain import IndustrialFacility, ThermalObservation


class DataProvider(ABC):
    name: str
    mode: str

    @abstractmethod
    def fetch_observations(self) -> list[ThermalObservation]:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "mode": self.mode, "ready": True}


class ContextProvider(ABC):
    name: str
    mode: str

    @abstractmethod
    def facilities_near(self, lat: float, lon: float, radius_m: float = 4000) -> list[IndustrialFacility] | None:
        """Return a list (possibly empty) when search ran, or None if context is unavailable."""

    def land_context(self, lat: float, lon: float) -> tuple[str | None, str, list[str]]:
        return None, "unknown", []

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "mode": self.mode, "ready": True}


class ImageryProvider(ABC):
    name: str
    mode: str

    def tile_url(self) -> str | None:
        return None

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "mode": self.mode, "ready": bool(self.tile_url())}


def parse_observation(raw: dict[str, Any], source: str) -> ThermalObservation:
    acquired = raw.get("acquired_at") or raw.get("acq_datetime")
    if isinstance(acquired, str):
        acquired_at = datetime.fromisoformat(acquired.replace("Z", "+00:00"))
    else:
        acquired_at = acquired
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=timezone.utc)
    return ThermalObservation(
        id=str(raw["id"]),
        latitude=float(raw["latitude"]),
        longitude=float(raw["longitude"]),
        acquired_at=acquired_at,
        brightness=_f(raw.get("brightness") if raw.get("brightness") is not None else raw.get("bright_ti4")),
        frp=_f(raw.get("frp")),
        confidence=raw.get("confidence"),
        sensor=raw.get("sensor") or raw.get("instrument"),
        satellite=raw.get("satellite"),
        day_night=raw.get("day_night") or raw.get("daynight"),
        scan=_f(raw.get("scan")),
        track=_f(raw.get("track")),
        source_dataset=raw.get("source_dataset"),
        observation_quality=raw.get("observation_quality"),
        source=source,
        provenance=raw.get("provenance") or {},
    )


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
