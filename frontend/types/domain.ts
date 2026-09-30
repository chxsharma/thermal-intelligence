export type ConfidenceBand = "HIGH" | "MEDIUM" | "LOW" | "UNRESOLVED";
export type Priority = "High" | "Medium" | "Low";

export interface EvidenceItem {
  polarity: string;
  code: string;
  feature?: string;
  actual_value?: string;
  effect?: string;
  explanation?: string;
  statement?: string;
  feature_name?: string | null;
  feature_value?: string | null;
}

export interface SourceCard {
  id: string;
  classification: string;
  classification_title: string;
  confidence: ConfidenceBand;
  priority: Priority;
  persistence_30d: number;
  active_days: number;
  nearest_facility_m: number | null;
  context_status: string;
  last_observation: string;
  first_observation: string;
  centroid: [number, number];
  review_status: string;
  review_recommended: boolean;
  scenario_name?: string | null;
  region?: string | null;
  observation_count: number;
}

export interface MapPayload {
  mode: string;
  as_of: string;
  last_firms_ingest_at?: string | null;
  metrics: {
    active_observations: number;
    source_clusters: number;
    industrial_candidates: number;
    persistent_sources: number;
    priority_reviews: number;
    data_freshness: string;
  };
  observations: Array<{
    id: string;
    lat: number;
    lon: number;
    acquired_at: string;
    frp: number | null;
    cluster_id: string | null;
    day_night: string | null;
  }>;
  clusters: Array<{
    id: string;
    lat: number;
    lon: number;
    label: string;
    title: string;
    confidence: ConfidenceBand;
    priority: Priority;
    persistence_30d: number;
    observation_count: number;
  }>;
  facilities: Array<{
    id: string;
    name: string;
    facility_type?: string | null;
    latitude: number;
    longitude: number;
  }>;
}

export const CLASS_COLOR: Record<string, string> = {
  abnormal_industrial_thermal_event: "#d4655a",
  persistent_industrial_thermal_source: "#d08a4a",
  vegetation_natural_fire: "#6ea56e",
  agricultural_burning: "#c9a227",
  other_unknown: "#c9a227",
  insufficient_evidence: "#8a93a0",
};

export function classGlyph(label: string): string {
  switch (label) {
    case "abnormal_industrial_thermal_event":
      return "ABN";
    case "persistent_industrial_thermal_source":
      return "PERS";
    case "vegetation_natural_fire":
      return "VEG";
    case "agricultural_burning":
      return "AGR";
    case "other_unknown":
      return "OTH";
    default:
      return "UNK";
  }
}

export function formatMeters(value: number | null | undefined, status?: string): string {
  if (status === "not_available" || status === "unknown") return "Context not available";
  if (status === "not_found") return "Not found in mapped extract";
  if (value == null) return "Unknown";
  if (value >= 1000) return `${(value / 1000).toFixed(2)} km`;
  return `${Math.round(value)} m`;
}

export function formatWhen(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }) + " UTC";
}
