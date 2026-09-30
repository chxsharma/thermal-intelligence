import { SourceCard } from "@/types/domain";

export interface SourceFilters {
  q: string;
  classification: string;
  confidence: string;
  priority: string;
  industrial: string;
  persistence: string;
  review: string;
  sort: string;
}

export const EMPTY_FILTERS: SourceFilters = {
  q: "",
  classification: "",
  confidence: "",
  priority: "",
  industrial: "",
  persistence: "",
  review: "",
  sort: "priority",
};

export function filterSources(cards: SourceCard[], filters: SourceFilters): SourceCard[] {
  let next = cards;
  const q = filters.q.trim().toLowerCase();
  if (q) {
    next = next.filter(
      (c) =>
        c.id.toLowerCase().includes(q) ||
        (c.scenario_name || "").toLowerCase().includes(q) ||
        (c.region || "").toLowerCase().includes(q)
    );
  }
  if (filters.classification) next = next.filter((c) => c.classification === filters.classification);
  if (filters.confidence) next = next.filter((c) => c.confidence === filters.confidence);
  if (filters.priority) next = next.filter((c) => c.priority === filters.priority);
  if (filters.review) next = next.filter((c) => c.review_status === filters.review);
  if (filters.industrial === "associated") {
    next = next.filter((c) => c.context_status === "available" && (c.nearest_facility_m ?? 1e9) <= 1000);
  } else if (filters.industrial) {
    next = next.filter((c) => c.context_status === filters.industrial);
  }
  if (filters.persistence === "persistent") next = next.filter((c) => c.active_days >= 14);
  if (filters.persistence === "short") next = next.filter((c) => c.active_days <= 3);
  const rankP: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
  const rankC: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2, UNRESOLVED: 3 };
  next = [...next];
  if (filters.sort === "persistence") next.sort((a, b) => b.persistence_30d - a.persistence_30d);
  else if (filters.sort === "latest") next.sort((a, b) => b.last_observation.localeCompare(a.last_observation));
  else if (filters.sort === "confidence") next.sort((a, b) => (rankC[a.confidence] ?? 9) - (rankC[b.confidence] ?? 9));
  else next.sort((a, b) => (rankP[a.priority] ?? 9) - (rankP[b.priority] ?? 9));
  return next;
}
