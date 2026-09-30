from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ThermalObservationRow(Base, TimestampMixin):
    __tablename__ = "thermal_observations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    frp: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    sensor: Mapped[str | None] = mapped_column(String, nullable=True)
    satellite: Mapped[str | None] = mapped_column(String, nullable=True)
    day_night: Mapped[str | None] = mapped_column(String, nullable=True)
    scan: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    observation_quality: Mapped[str | None] = mapped_column(String, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class SourceClusterRow(Base, TimestampMixin):
    __tablename__ = "source_clusters"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    observation_count: Mapped[int] = mapped_column(Integer)
    active_days: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    persistence_7d: Mapped[int] = mapped_column(Integer)
    persistence_14d: Mapped[int] = mapped_column(Integer)
    persistence_30d: Mapped[int] = mapped_column(Integer)
    persistence_90d: Mapped[int] = mapped_column(Integer)
    spatial_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    intensity_statistics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class IndustrialFacilityRow(Base, TimestampMixin):
    __tablename__ = "industrial_facilities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    facility_type: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    osm_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ContextFeatureRow(Base, TimestampMixin):
    __tablename__ = "context_features"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    cluster_id: Mapped[str] = mapped_column(String)
    nearest_industrial_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    industrial_count_1km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    industrial_count_2km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    osm_object_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    land_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_status: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
