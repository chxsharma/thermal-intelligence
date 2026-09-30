from __future__ import annotations

from typing import Any

from app.schemas.domain import FeatureVector, ThermalObservation


def observation_lineage(obs: ThermalObservation) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "dataset", "label": obs.source_dataset or "FIRMS / upload / demo"},
            {"id": "observation", "label": "Thermal observation"},
            {"id": "context", "label": "OSM / industrial context"},
            {"id": "temporal", "label": "Temporal history"},
            {"id": "features", "label": "Feature engineering"},
            {"id": "engine", "label": "Evidence Engine"},
            {"id": "class", "label": "Classification"},
        ],
        "edges": [
            ["dataset", "observation"],
            ["observation", "context"],
            ["context", "temporal"],
            ["temporal", "features"],
            ["features", "engine"],
            ["engine", "class"],
        ],
        "provenance": {
            "source_dataset": obs.source_dataset,
            "sensor": obs.sensor,
            "satellite": obs.satellite,
            "observation_timestamp": obs.acquired_at.isoformat(),
            "processing_timestamp": obs.provenance.get("processed_at"),
            "provider": obs.source,
            "dataset_version": obs.provenance.get("dataset_version"),
        },
    }


def feature_lineage(features: FeatureVector) -> dict[str, Any]:
    return {
        "feature_schema_version": "features-1.0",
        "context_status": features.context_status,
        "completeness": features.context_completeness,
        "values": features.model_dump(mode="json"),
    }
