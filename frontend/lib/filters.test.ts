import { describe, expect, it } from "vitest";
import { filterSources, EMPTY_FILTERS } from "./filters";
import { SourceCard } from "@/types/domain";

function card(partial: Partial<SourceCard>): SourceCard {
  return {
    id: "SRC-1",
    classification: "insufficient_evidence",
    classification_title: "Insufficient Evidence",
    confidence: "UNRESOLVED",
    priority: "Low",
    persistence_30d: 1,
    active_days: 1,
    nearest_facility_m: null,
    context_status: "not_available",
    last_observation: "2026-09-12T00:00:00Z",
    first_observation: "2026-09-12T00:00:00Z",
    centroid: [26, 71],
    review_status: "system_recommendation",
    review_recommended: true,
    scenario_name: "Uncertain hotspot",
    region: "Rajasthan",
    observation_count: 1,
    ...partial,
  };
}

describe("filterSources", () => {
  const rows = [
    card({ id: "SRC-A", priority: "High", classification: "abnormal_industrial_thermal_event" }),
    card({ id: "SRC-B", priority: "Low", scenario_name: "Persistent refinery thermal source", classification: "persistent_industrial_thermal_source", confidence: "HIGH" }),
  ];

  it("filters by query", () => {
    const found = filterSources(rows, { ...EMPTY_FILTERS, q: "refinery" });
    expect(found.map((r) => r.id)).toEqual(["SRC-B"]);
  });

  it("sorts by priority", () => {
    const found = filterSources(rows, EMPTY_FILTERS);
    expect(found[0].id).toBe("SRC-A");
  });
});
