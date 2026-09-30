-- THERMAL // INTELLIGENCE
-- PostgreSQL schema (SQLite-compatible types noted in comments)

CREATE TABLE IF NOT EXISTS data_ingestion_runs (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    provenance JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_versions (
    id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    version TEXT NOT NULL,
    feature_schema_version TEXT NOT NULL,
    evaluated BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS industrial_facilities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    facility_type TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    osm_id TEXT,
    source TEXT NOT NULL,
    provenance JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thermal_observations (
    id TEXT PRIMARY KEY,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    brightness DOUBLE PRECISION,
    frp DOUBLE PRECISION,
    confidence TEXT,
    sensor TEXT,
    satellite TEXT,
    day_night TEXT,
    scan DOUBLE PRECISION,
    track DOUBLE PRECISION,
    source_dataset TEXT,
    observation_quality TEXT,
    cluster_id TEXT,
    source TEXT NOT NULL,
    provenance JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_obs_time ON thermal_observations (acquired_at);
CREATE INDEX IF NOT EXISTS idx_obs_cluster ON thermal_observations (cluster_id);

CREATE TABLE IF NOT EXISTS source_clusters (
    id TEXT PRIMARY KEY,
    centroid_lat DOUBLE PRECISION NOT NULL,
    centroid_lon DOUBLE PRECISION NOT NULL,
    observation_count INTEGER NOT NULL,
    active_days INTEGER NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    persistence_7d INTEGER NOT NULL,
    persistence_14d INTEGER NOT NULL,
    persistence_30d INTEGER NOT NULL,
    persistence_90d INTEGER NOT NULL,
    spatial_stability DOUBLE PRECISION,
    intensity_statistics JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS context_features (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    nearest_industrial_distance_m DOUBLE PRECISION,
    industrial_count_1km INTEGER,
    industrial_count_2km INTEGER,
    osm_object_types JSONB,
    land_context TEXT,
    context_completeness DOUBLE PRECISION,
    context_status TEXT NOT NULL,
    source TEXT NOT NULL,
    provenance JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS temporal_records (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    detections_7d INTEGER NOT NULL,
    detections_14d INTEGER NOT NULL,
    detections_30d INTEGER NOT NULL,
    detections_90d INTEGER NOT NULL,
    active_days INTEGER NOT NULL,
    intensity_trend TEXT,
    day_count INTEGER NOT NULL,
    night_count INTEGER NOT NULL,
    provenance JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS classifications (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence_band TEXT NOT NULL,
    priority TEXT NOT NULL,
    internal_score DOUBLE PRECISION,
    classifier_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    polarity TEXT NOT NULL,
    code TEXT NOT NULL,
    statement TEXT NOT NULL,
    feature_name TEXT,
    feature_value TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_actions (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    action TEXT NOT NULL,
    previous_label TEXT,
    new_label TEXT,
    note TEXT,
    analyst TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyst_notes (
    id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    body TEXT NOT NULL,
    analyst TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    cluster_id TEXT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    priority TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
