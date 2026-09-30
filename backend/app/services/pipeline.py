from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.classification.engine import EvidenceBaselineClassifier, LABEL_TITLES
from app.clustering.engine import cluster_observations, cluster_summary, clustering_diagnostics
from app.config import get_settings
from app.context.enrichment import ContextEnrichmentProvider
from app.features.engineering import FEATURE_SCHEMA_VERSION, build_feature_vector
from app.geo import haversine_m
from app.providers.demo import DemoContextProvider, DemoDataProvider, DemoImageryProvider
from app.providers.live import FirmsDataProvider
from app.provenance.lineage import observation_lineage
from app.schemas.domain import ClassificationResult, IndustrialFacility, ThermalObservation


def _redact_secret(text: str, secret: str) -> str:
    if secret:
        return text.replace(secret, "<MAP_KEY>")
    return text


class IntelligenceStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.classifier = EvidenceBaselineClassifier()
        self.reviews: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.ingestion_runs: list[dict[str, Any]] = []
        self.uploaded_batches: list[str] = []
        self.live_attempted = False
        self.live_error: str | None = None
        self.last_firms_ok_at: datetime | None = None
        self.reload()

    def reload(self, extra_observations: list[ThermalObservation] | None = None) -> None:
        get_settings.cache_clear()
        self.settings = get_settings()
        self.demo_data = DemoDataProvider()
        self.demo_context = DemoContextProvider()
        self.imagery = DemoImageryProvider()
        observations = self.demo_data.fetch_observations()
        mode = "DEMO REPLAY MODE"
        provider_name = self.demo_data.name
        self.live_attempted = bool(self.settings.firms_map_key) and self.settings.app_mode.lower() == "live"
        if self.live_attempted:
            try:
                observations = FirmsDataProvider().fetch_observations()
                mode = "LIVE NASA FIRMS"
                provider_name = "FirmsDataProvider"
                self.live_error = None
                self.last_firms_ok_at = datetime.now(timezone.utc)
            except Exception as exc:  # noqa: BLE001 — demo fallback is required
                self.live_error = _redact_secret(str(exc), self.settings.firms_map_key)
                mode = "DEMO REPLAY MODE"
                provider_name = "DemoDataProvider (fallback)"
        if extra_observations:
            observations = observations + extra_observations
        self.mode = mode
        self.data_provider_name = provider_name
        if mode.startswith("LIVE"):
            from app.providers.live import OSMContextProvider

            osm = OSMContextProvider()
            self.context_enrichment = ContextEnrichmentProvider(primary=osm, fallback=None)
            self.context_provider = osm
            self.context_mode = osm.mode
        else:
            self.context_enrichment = ContextEnrichmentProvider(primary=self.demo_context, fallback=self.demo_context)
            self.context_provider = self.demo_context
            self.context_mode = "DEMO REPLAY MODE"
        self.observations = observations
        grouped = cluster_observations(
            observations,
            spatial_threshold_m=self.settings.cluster_spatial_radius_m,
            temporal_gap_hours=self.settings.cluster_temporal_gap_hours,
        )
        self.clusters_obs = grouped
        as_of = max((o.acquired_at for o in observations), default=datetime.now(timezone.utc))
        self.as_of = as_of
        centroids: list[tuple[str, float, float]] = []
        for cluster_id, members in grouped.items():
            summary = cluster_summary(cluster_id, members, as_of=as_of)
            centroids.append((cluster_id, summary["centroid_lat"], summary["centroid_lon"]))
        if mode.startswith("LIVE"):
            from app.context.sample import pinned_live_demo_cluster_ids, sample_live_osm_clusters

            sample = sample_live_osm_clusters(
                centroids,
                int(self.settings.osm_validation_cluster_limit),
                pinned_live_demo_cluster_ids(),
            )
            self.context_enrichment.set_scope({cid for cid, _lat, _lon in sample})
            self.context_enrichment.prefetch(sample)
        else:
            self.context_enrichment.prefetch(centroids)
        self.cluster_docs: dict[str, dict[str, Any]] = {}
        for cluster_id, obs in grouped.items():
            self.cluster_docs[cluster_id] = self._build_cluster(cluster_id, obs, as_of)
        mapped = self.context_enrichment.map_facilities()
        self.facilities = mapped if mode.startswith("LIVE") else self.demo_context.all_facilities()
        self._rebuild_alerts()
        self.ingestion_runs.append(
            {
                "id": f"ING-{len(self.ingestion_runs)+1:03d}",
                "provider": provider_name,
                "mode": mode,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "observation_count": len(observations),
                "error_message": self.live_error,
                "provenance": {"feature_schema_version": FEATURE_SCHEMA_VERSION},
            }
        )

    def _build_cluster(self, cluster_id: str, obs: list[ThermalObservation], as_of: datetime) -> dict[str, Any]:
        visible = [o for o in obs if o.acquired_at <= as_of]
        in_window = bool(visible)
        if not visible:
            visible = [min(obs, key=lambda o: (o.acquired_at, o.id))]
        summary = cluster_summary(cluster_id, visible, as_of=as_of)
        scene = None if self.mode.startswith("LIVE") else self.demo_context.scenario_for_cluster_obs([o.id for o in visible])
        lat, lon = summary["centroid_lat"], summary["centroid_lon"]
        ctx = self.context_enrichment.enrich(cluster_id, lat, lon)
        if scene and scene.get("context_status") == "not_available":
            facilities: list[IndustrialFacility] | None = None
            land, status, osm_types = scene.get("land_context"), "not_available", scene.get("osm_object_types") or []
        elif scene:
            nearby = self.demo_context.facilities_near(lat, lon)
            land, status, osm_types = scene.get("land_context"), scene.get("context_status", "available"), scene.get("osm_object_types") or []
            facilities = nearby
        else:
            facilities = ctx.facilities
            land, status, osm_types = ctx.land_context, ctx.context_status, ctx.osm_object_types
        features = build_feature_vector(
            cluster_id,
            visible,
            facilities,
            as_of=as_of,
            land_context=land,
            osm_types=osm_types,
            context_status=status,
        )
        classification = self.classifier.classify(features)
        nearby_facilities = facilities or []
        last_obs = max(visible, key=lambda o: o.acquired_at)
        review = self._latest_review(cluster_id)
        return {
            "summary": {
                **summary,
                "first_seen": summary["first_seen"].isoformat(),
                "last_seen": summary["last_seen"].isoformat(),
                "observation_count": 0 if not in_window else summary["observation_count"],
                "active_days": 0 if not in_window else summary["active_days"],
            },
            "features": features.model_dump(mode="json"),
            "classification": classification.model_dump(mode="json"),
            "classification_title": LABEL_TITLES[classification.label],
            "scenario": scene,
            "nearby_facilities": [f.model_dump(mode="json") for f in nearby_facilities],
            "observations": [] if not in_window else [o.model_dump(mode="json") for o in visible],
            "lineage": observation_lineage(last_obs),
            "review": review,
            "final_label": (review or {}).get("new_label") or classification.label,
            "final_status": (review or {}).get("action") or "system_recommendation",
        }

    def snapshot(self, as_of: datetime | None = None) -> dict[str, Any]:
        moment = as_of or self.as_of
        docs = {}
        for cluster_id, obs in self.clusters_obs.items():
            visible = [o for o in obs if o.acquired_at <= moment]
            if not visible:
                continue
            docs[cluster_id] = self._build_cluster(cluster_id, obs, moment)
        observations = [o for o in self.observations if o.acquired_at <= moment]
        return {
            "as_of": moment.isoformat(),
            "mode": self.mode,
            "last_firms_ingest_at": self.last_firms_ok_at.isoformat() if self.last_firms_ok_at else None,
            "clusters": list(docs.values()),
            "observations": [o.model_dump(mode="json") for o in observations],
            "metrics": self._metrics(docs, observations, moment),
        }

    def _metrics(self, docs: dict[str, dict], observations: list[ThermalObservation], moment: datetime) -> dict[str, Any]:
        classifications = [d["classification"]["label"] for d in docs.values()]
        return {
            "active_observations": len(observations),
            "source_clusters": len(docs),
            "industrial_candidates": sum(
                1
                for d in docs.values()
                if d["classification"]["label"]
                in {"persistent_industrial_thermal_source", "abnormal_industrial_thermal_event"}
            ),
            "persistent_sources": sum(1 for d in docs.values() if d["classification"]["label"] == "persistent_industrial_thermal_source"),
            "priority_reviews": sum(1 for d in docs.values() if d["classification"]["review_recommended"]),
            "data_freshness": moment.isoformat(),
            "classification_counts": {
                key: classifications.count(key)
                for key in sorted(set(classifications))
            },
        }

    def source_cards(self) -> list[dict[str, Any]]:
        cards = []
        for doc in self.cluster_docs.values():
            summary = doc["summary"]
            clf = doc["classification"]
            feat = doc["features"]
            nearest = feat.get("nearest_industrial_distance")
            cards.append(
                {
                    "id": summary["id"],
                    "classification": clf["label"],
                    "classification_title": doc["classification_title"],
                    "confidence": clf["confidence_band"],
                    "priority": clf["priority"],
                    "persistence_30d": summary["persistence_30d"],
                    "active_days": summary["active_days"],
                    "nearest_facility_m": nearest,
                    "context_status": feat.get("context_status"),
                    "last_observation": summary["last_seen"],
                    "first_observation": summary["first_seen"],
                    "centroid": [summary["centroid_lat"], summary["centroid_lon"]],
                    "review_status": doc["final_status"],
                    "review_recommended": clf["review_recommended"],
                    "scenario_name": (doc["scenario"] or {}).get("name"),
                    "region": (doc["scenario"] or {}).get("region"),
                    "observation_count": summary["observation_count"],
                }
            )
        return cards

    def _latest_review(self, cluster_id: str) -> dict[str, Any] | None:
        items = [r for r in self.reviews if r["cluster_id"] == cluster_id]
        return items[-1] if items else None

    def add_review(self, cluster_id: str, action: str, analyst: str, note: str | None, new_label: str | None) -> dict[str, Any]:
        doc = self.cluster_docs[cluster_id]
        record = {
            "id": f"REV-{len(self.reviews)+1:04d}",
            "cluster_id": cluster_id,
            "action": action,
            "previous_label": doc["final_label"],
            "new_label": new_label or doc["final_label"],
            "note": note,
            "analyst": analyst,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.reviews.append(record)
        if note:
            self.notes.append(
                {
                    "id": f"NOTE-{len(self.notes)+1:04d}",
                    "cluster_id": cluster_id,
                    "body": note,
                    "analyst": analyst,
                    "created_at": record["created_at"],
                }
            )
        self.cluster_docs[cluster_id] = self._build_cluster(cluster_id, self.clusters_obs[cluster_id], self.as_of)
        return record

    def _rebuild_alerts(self) -> None:
        alerts = []
        for doc in self.cluster_docs.values():
            clf = doc["classification"]
            cid = doc["summary"]["id"]
            title = doc["classification_title"]
            if clf["label"] == "abnormal_industrial_thermal_event":
                alerts.append(
                    {
                        "id": f"ALRT-{cid}-ABN",
                        "cluster_id": cid,
                        "kind": "abnormal_industrial_candidate",
                        "title": "Potential industrial event requiring review",
                        "body": f"{title} with {clf['confidence_band']} confidence. Evidence suggests spatial association with industry; causality is not established.",
                        "priority": "High",
                    }
                )
            elif clf["label"] == "persistent_industrial_thermal_source" and doc["summary"]["persistence_30d"] >= 10:
                alerts.append(
                    {
                        "id": f"ALRT-{cid}-PERS",
                        "cluster_id": cid,
                        "kind": "persistent_threshold",
                        "title": "Persistent source crossed monitoring threshold",
                        "body": f"{doc['summary']['persistence_30d']} detections in 30 days at a spatially stable industrial location.",
                        "priority": "Medium",
                    }
                )
            elif clf["review_recommended"]:
                alerts.append(
                    {
                        "id": f"ALRT-{cid}-REV",
                        "cluster_id": cid,
                        "kind": "unresolved_review",
                        "title": "Unresolved source requiring analyst attention",
                        "body": "; ".join(clf["review_reasons"]) or "Low-confidence or incomplete evidence.",
                        "priority": clf["priority"],
                    }
                )
        self.alerts = alerts

    def health(self) -> dict[str, Any]:
        last = self.ingestion_runs[-1] if self.ingestion_runs else None
        return {
            "mode": self.mode,
            "never_live_in_replay": not self.mode.startswith("LIVE"),
            "last_firms_ingest_at": self.last_firms_ok_at.isoformat() if self.last_firms_ok_at else None,
            "data_provider": {"name": self.data_provider_name, "mode": self.mode, "error": self.live_error},
            "context_provider": {"name": getattr(self.context_provider, "name", "demo"), "mode": self.context_mode},
            "imagery_provider": self.imagery.status(),
            "last_ingestion": last,
            "observation_count": len(self.observations),
            "clustering_diagnostics": clustering_diagnostics(
                self.clusters_obs,
                spatial_threshold_m=self.settings.cluster_spatial_radius_m,
                temporal_gap_hours=self.settings.cluster_temporal_gap_hours,
            ),
            "context_diagnostics": self._context_diagnostics(),
            "data_freshness": self.as_of.isoformat() if self.observations else None,
            "classifier_provider": self.classifier.name,
            "classifier_version": self.classifier.version,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "evaluation_status": "Evaluation not yet performed.",
            "database": self.settings.database_url.split("://")[0],
            "api_status": "ok",
        }

    def _context_diagnostics(self) -> dict[str, Any]:
        statuses = [d["features"].get("context_status") for d in self.cluster_docs.values()]
        meta = self.context_enrichment.diagnostics()
        provider_failed = sum(
            1
            for ctx in self.context_enrichment._cluster_cache.values()
            if ctx.context_status == "not_available" and ctx.provider_error
        )
        return {
            "provider": getattr(self.context_provider, "name", "unknown"),
            "mode": self.context_mode,
            "fallback_provider": meta.get("fallback_provider"),
            "fallback_used": meta.get("fallback_used"),
            "clusters_enriched": len(statuses),
            "clusters_with_industrial_context": sum(1 for s in statuses if s == "available"),
            "clusters_not_found": sum(1 for s in statuses if s == "not_found"),
            "clusters_not_available": sum(1 for s in statuses if s == "not_available"),
            "clusters_unknown": sum(1 for s in statuses if s not in {"available", "not_found", "not_available"}),
            "clusters_unavailable_due_to_provider_failure": provider_failed,
            "overpass_queries": getattr(self.context_provider, "query_count", 0),
            "cache_hits": meta.get("cache_hits"),
            "last_error": meta.get("last_error"),
            "note": meta.get("note"),
        }

    def analytics(self) -> dict[str, Any]:
        cards = self.source_cards()
        persistence_buckets = {"1": 0, "2-7": 0, "8-30": 0, "31+": 0}
        for card in cards:
            days = card["active_days"]
            if days <= 1:
                persistence_buckets["1"] += 1
            elif days <= 7:
                persistence_buckets["2-7"] += 1
            elif days <= 30:
                persistence_buckets["8-30"] += 1
            else:
                persistence_buckets["31+"] += 1
        industrial_assoc = {"associated": 0, "not_found": 0, "not_available": 0}
        for card in cards:
            status = card["context_status"]
            if status == "available" and card["nearest_facility_m"] is not None and card["nearest_facility_m"] <= 1000:
                industrial_assoc["associated"] += 1
            elif status == "not_found":
                industrial_assoc["not_found"] += 1
            else:
                industrial_assoc["not_available"] += 1
        by_day: dict[str, int] = {}
        for obs in self.observations:
            day = obs.acquired_at.date().isoformat()
            by_day[day] = by_day.get(day, 0) + 1
        return {
            "classification_distribution": {
                c["classification_title"]: sum(1 for x in cards if x["classification"] == c["classification"])
                for c in cards
            },
            "confidence_distribution": {
                band: sum(1 for c in cards if c["confidence"] == band) for band in ["HIGH", "MEDIUM", "LOW", "UNRESOLVED"]
            },
            "persistence_distribution": persistence_buckets,
            "industrial_context_association": industrial_assoc,
            "review_queue_volume": sum(1 for c in cards if c["review_recommended"]),
            "regional_source_density": [
                {"id": c["id"], "region": c["region"], "count": c["observation_count"], "lat": c["centroid"][0], "lon": c["centroid"][1]}
                for c in cards
            ],
            "temporal_trends": [{"date": k, "observations": by_day[k]} for k in sorted(by_day)],
            "evaluation": {
                "status": "Evaluation not yet performed.",
                "precision": None,
                "recall": None,
                "f1": None,
                "confusion_matrix": None,
                "per_class": None,
            },
        }

    def facility_brief(self, facility_id: str) -> dict[str, Any]:
        facility = next(f for f in self.facilities if f.id == facility_id)
        nearby = []
        for doc in self.cluster_docs.values():
            dist = haversine_m(
                facility.latitude,
                facility.longitude,
                doc["summary"]["centroid_lat"],
                doc["summary"]["centroid_lon"],
            )
            if dist <= 5000:
                nearby.append(
                    {
                        "cluster_id": doc["summary"]["id"],
                        "distance_m": dist,
                        "classification": doc["classification_title"],
                        "persistence_30d": doc["summary"]["persistence_30d"],
                        "last_seen": doc["summary"]["last_seen"],
                    }
                )
        nearby.sort(key=lambda x: x["distance_m"])
        return {
            "facility": facility.model_dump(mode="json"),
            "nearby_sources": nearby,
            "language": "Shows spatial association and historical co-location only. This does not establish that the facility caused thermal detections.",
        }


STORE = IntelligenceStore()
