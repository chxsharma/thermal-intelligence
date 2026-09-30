export type ClusterSummary = {
  id: string;
  scenario_id?: string | null;
  centroid: { lat: number; lon: number };
  observation_count: number;
  active_days: number;
  first_seen: string;
  last_seen: string;
  persistence_7d: number;
  persistence_14d?: number;
  persistence_30d: number;
  persistence_90d?: number;
  spatial_stability: number | null;
  intensity_mean?: number | null;
  intensity_max?: number | null;
  intensity_trend?: string | null;
  region?: string | null;
  label: string;
  label_text: string;
  confidence_band: string;
  priority: string;
  review_status: string;
  final_label?: string | null;
  nearest_facility_m: number | null;
  context_status: string;
  land_context?: string | null;
};

export type Observation = {
  id: string;
  lat: number;
  lon: number;
  acquired_at: string;
  brightness?: number | null;
  frp?: number | null;
  confidence?: string | null;
  sensor?: string | null;
  satellite?: string | null;
  day_night?: string | null;
  source_dataset?: string | null;
  cluster_id?: string | null;
  provenance?: Record<string, unknown> | null;
};

export type Evidence = { key: string; label: string; value: string; polarity?: string };
