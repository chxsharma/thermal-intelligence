from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


def _demo_dir() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "data" / "demo",
        here.parents[1].parent / "data" / "demo",
        Path.cwd().parent / "data" / "demo",
        Path.cwd() / "data" / "demo",
    ]
    for path in candidates:
        if (path / "observations.json").exists():
            return path
    return candidates[0]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", Path(".env")), extra="ignore")

    app_mode: str = "demo"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    analyst_write_token: str = "dev-review-token"
    database_url: str = "sqlite:///./data/local/thermal.db"
    firms_map_key: str = ""
    firms_source: str = "VIIRS_SNPP_NRT"
    firms_days: int = 5
    firms_bbox: str = "68.0,8.0,97.5,37.5"
    firms_historical_source: str = "VIIRS_SNPP_NRT"
    firms_historical_days: int = 30
    firms_historical_bbox: str = "69.80,22.30,70.00,22.45"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    context_cache_ttl_seconds: int = 3600
    overpass_timeout_seconds: float = 25.0
    overpass_batch_size: int = 12
    overpass_inter_batch_sleep_s: float = 8.0
    osm_validation_cluster_limit: int = 10
    satellite_tile_url: str = ""
    cluster_spatial_radius_m: float = 1000.0
    cluster_temporal_gap_hours: float = 48.0
    demo_dir: Path = _demo_dir()
    upload_dir: Path = ROOT / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
