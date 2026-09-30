# Classification — Evidence Engine

The production path is `EvidenceBaselineClassifier` (UI label: **Evidence Engine**). It is not a trained model. Random forest, gradient boosting, and remote model classes exist only as unconnected interfaces; calling them raises `NotImplementedError`.

## Why evidence-based first

There is no labelled SIH26162 training set in this repository. Publishing F1/AUC would be fabrication. A transparent score over documented features is auditable by an analyst in 90 seconds.

## Features (`features-1.0`)

| Feature | Meaning |
|---|---|
| brightness / FRP / confidence | Thermal intensity and sensor quality; omitted if missing |
| day_night, day_count, night_count | Timing mix; not a physical process label |
| observation_count, detections_7/14/30/90d, active_days | Persistence of *detections*, not of a fire |
| spatial_stability | Inverse of mean radius about centroid |
| nearest_industrial_distance, counts 1km/2km | Spatial association with mapped OSM/demo facilities |
| land_context | Recorded class (industrial, forest, cropland, mixed, null) |
| source_density | Detections per span day |
| context_completeness / context_status | How much context actually arrived |

## Proximity is not causality

A 420 m offset to a refinery supports the sentence “spatially associated with a mapped industrial facility.” It does not support “this facility caused the fire.” Counter-evidence records missing overlap, missing context, and conflicting land class.

## Persistence is not an accident

Repeated, spatially stable detections next to a refinery more strongly support **Persistent Industrial Thermal Source** (flare, furnace, routine heat) than **Abnormal Industrial Thermal Event**. Abnormal scores are reduced when `active_days` and 30-day counts are high.

## Uncertainty

Outputs are bands: HIGH / MEDIUM / LOW / UNRESOLVED. An internal 0–1 score exists for ranking only; the UI does not present it as a calibrated probability. Sparse observations, missing FRP/confidence, or unavailable OSM context push toward Insufficient Evidence / UNRESOLVED and the review queue.

## Why-not text

Each alternative (wildfire, agricultural burning, industrial source) is generated from the same features. The engine never invents a reason that is not grounded in a field.
