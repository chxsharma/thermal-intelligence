# Data model

Entities (also in `data/schemas/postgres.sql`):

- `thermal_observations` — FIRMS-like points. Fields may be null (`frp`, `confidence`, `scan`, `track`, quality).
- `source_clusters` — centroid, counts, persistence windows, spatial stability, intensity stats.
- `industrial_facilities` — mapped context, not causes.
- `context_features` — distances, counts, OSM types, `context_status`, completeness.
- `temporal_records` — as-of snapshots for replay.
- `classifications` — label, confidence band, priority, classifier version.
- `evidence_items` — supporting or counter, with feature name/value.
- `review_actions` / `analyst_notes` — audit trail.
- `alerts` — derived operational cues.
- `data_ingestion_runs` / `model_versions` — health.

`context_status` is one of:

- `available` — a search ran and returned usable industrial context  
- `not_found` — a search ran and found no mapped facility  
- `not_available` / `unknown` — search did not run or failed  

`not_available` must **not** be stored as zero facilities.

Observation identity ≠ cluster identity ≠ investigated event. A persistent industrial source can exist without an “event”. Uploaded CSV rows are parsed only if `latitude`, `longitude`, and acquisition date/time are present.
