from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import ClassificationResult, EvidenceItem, FeatureVector

LABEL_ABNORMAL = "abnormal_industrial_thermal_event"
LABEL_PERSISTENT = "persistent_industrial_thermal_source"
LABEL_VEGETATION = "vegetation_natural_fire"
LABEL_AGRICULTURE = "agricultural_burning"
LABEL_OTHER = "other_unknown"
LABEL_INSUFFICIENT = "insufficient_evidence"

LABEL_TITLES = {
    LABEL_ABNORMAL: "Abnormal Industrial Thermal Event",
    LABEL_PERSISTENT: "Persistent Industrial Thermal Source",
    LABEL_VEGETATION: "Vegetation / Natural Fire",
    LABEL_AGRICULTURE: "Agricultural Burning",
    LABEL_OTHER: "Other / Unknown",
    LABEL_INSUFFICIENT: "Insufficient Evidence",
}

CLASSIFIER_NAME = "Evidence Baseline"
CLASSIFIER_VERSION = "evidence-baseline-1.1"


class ClassifierProvider(ABC):
    """Pluggable classifier. Future RF / XGBoost / LightGBM providers implement this."""

    name: str
    version: str

    @abstractmethod
    def classify(self, features: FeatureVector) -> ClassificationResult:
        raise NotImplementedError


def get_classifier(provider: str | None = None) -> ClassifierProvider:
    """Factory for the active classifier. Untrained ML names are rejected, not faked."""
    key = (provider or "evidence-baseline").strip().lower()
    if key in {"evidence-baseline", "evidence", "baseline", ""}:
        return EvidenceBaselineClassifier()
    if key in {"random-forest", "rf"}:
        return RandomForestClassifierProvider()
    if key in {"xgboost", "lightgbm", "gbdt", "gradient-boosting"}:
        return GradientBoostingClassifierProvider()
    raise ValueError(f"Unknown classifier provider: {provider}")


def _fmt_m(value: float | None) -> str:
    if value is None:
        return "not available"
    if value >= 1000:
        return f"{value / 1000:.2f} km"
    return f"{value:.0f} m"


def _ev(polarity: str, code: str, feature: str, actual_value: str, effect: str, explanation: str) -> EvidenceItem:
    return EvidenceItem(
        polarity=polarity,
        code=code,
        feature=feature,
        actual_value=actual_value,
        effect=effect,
        explanation=explanation,
        feature_name=feature,
        feature_value=actual_value,
        statement=f"{effect}. {explanation}",
    )


class EvidenceBaselineClassifier(ClassifierProvider):
    """Transparent rule/score baseline. Not a trained ML model."""

    name = CLASSIFIER_NAME
    version = CLASSIFIER_VERSION

    def classify(self, features: FeatureVector) -> ClassificationResult:
        supporting: list[EvidenceItem] = []
        counter: list[EvidenceItem] = []
        review_reasons: list[str] = []

        industrial_known = features.context_status == "available"
        industrial_missing = features.context_status in {"not_available", "unknown"}
        industrial_not_found = features.context_status == "not_found"
        near_industry = (
            industrial_known
            and features.nearest_industrial_distance is not None
            and features.nearest_industrial_distance <= 1000
        )
        very_near_industry = (
            industrial_known
            and features.nearest_industrial_distance is not None
            and features.nearest_industrial_distance <= 500
        )
        span_h = features.observed_duration_hours
        span_d = features.observed_duration_days
        historical = features.historical_persistence_available
        short_event = features.active_days <= 2 and features.observation_count <= 8 and span_d <= 3
        repeated_in_window = features.active_days >= 3 and features.observation_count >= 5
        high_stability = features.spatial_stability is not None and features.spatial_stability >= 0.7
        low_stability = features.spatial_stability is not None and features.spatial_stability <= 0.35
        land = (features.land_context or "").lower()
        veg_land = any(k in land for k in ("forest", "vegetation", "grassland", "shrub", "wildland"))
        crop_land = any(k in land for k in ("crop", "agriculture", "farm", "stubble"))
        industrial_land = any(k in land for k in ("industrial", "refinery", "urban"))
        night_heavy = features.night_count >= max(2, features.day_count)
        day_heavy = features.day_count >= max(2, features.night_count)
        sparse = features.observation_count <= 2
        missing_thermal = features.missing_frp or features.missing_confidence
        osm_industrial_phrase = "osm-mapped industrial" in land

        if industrial_known and features.nearest_industrial_distance is not None:
            supporting.append(
                _ev(
                    "support",
                    "industrial_distance",
                    "industrial_facility_distance",
                    _fmt_m(features.nearest_industrial_distance),
                    "supports industrial association",
                    "A mapped industrial facility is spatially associated with the thermal cluster. Proximity is not causation.",
                )
            )
            supporting.append(
                _ev(
                    "support",
                    "industrial_count",
                    "industrial_count_1km",
                    str(features.industrial_count_1km),
                    "supports industrial association",
                    f"Mapped industrial features within 1 km: {features.industrial_count_1km}; within 2 km: {features.industrial_count_2km}.",
                )
            )
        elif industrial_not_found:
            counter.append(
                _ev(
                    "counter",
                    "no_mapped_facility",
                    "context_status",
                    "not_found",
                    "weakens industrial classification",
                    "Industrial context search completed and no mapped facility was found nearby. This is not proof that no facility exists.",
                )
            )
        elif industrial_missing:
            counter.append(
                _ev(
                    "counter",
                    "context_unavailable",
                    "context_status",
                    features.context_status,
                    "critical context missing",
                    "Industrial / OSM context is not available for this source. Absence of a facility record is not evidence that no facility exists.",
                )
            )
            review_reasons.append("missing context")

        supporting.append(
            _ev(
                "support",
                "temporal_window",
                "detections_in_window",
                str(features.detections_in_window or features.observation_count),
                "describes the observed window",
                (
                    f"{features.observation_count} detections, {features.active_days} active days, "
                    f"observed duration {span_h:.1f} h ({span_d:.2f} d)."
                ),
            )
        )
        if not historical:
            counter.append(
                _ev(
                    "counter",
                    "short_archive",
                    "historical_persistence_available",
                    "false",
                    "blocks multi-week persistence claims",
                    features.window_note or "Historical persistence unavailable for current live window.",
                )
            )
        if features.spatial_stability is not None:
            item = _ev(
                "support" if high_stability else "counter" if low_stability else "support",
                "stability",
                "spatial_stability",
                f"{features.spatial_stability:.2f}",
                "tight source footprint" if high_stability else "high spatial uncertainty" if low_stability else "moderate spatial grouping",
                "Spatial stability index (1.0 = tightly co-located). Dispersion is not a wildfire proof.",
            )
            (counter if low_stability else supporting).append(item)
        if features.frp is not None:
            supporting.append(
                _ev(
                    "support",
                    "frp",
                    "frp",
                    f"{features.frp:.1f} MW",
                    "thermal intensity present",
                    "Mean FRP among observations that include FRP. Intensity is not a class by itself.",
                )
            )
        else:
            counter.append(
                _ev(
                    "counter",
                    "missing_frp",
                    "frp",
                    "not available",
                    "weak thermal evidence",
                    "FRP is missing; intensity-based arguments are withheld.",
                )
            )
            review_reasons.append("poor observation quality")
        if features.missing_confidence:
            counter.append(
                _ev(
                    "counter",
                    "missing_confidence",
                    "confidence",
                    "not available",
                    "weak thermal confidence",
                    "Sensor confidence is missing; observation quality is incomplete.",
                )
            )
        elif features.confidence is not None and features.confidence < 40:
            counter.append(
                _ev(
                    "counter",
                    "low_confidence",
                    "confidence",
                    f"{features.confidence:.1f}",
                    "weak thermal confidence",
                    "Mean mapped sensor confidence is low.",
                )
            )
        if features.land_context and not (osm_industrial_phrase and not industrial_known):
            supporting.append(
                _ev(
                    "support",
                    "land",
                    "land_context",
                    features.land_context,
                    "contextual land description",
                    "Recorded land/context class is supporting context, not ground truth.",
                )
            )
        if features.night_count or features.day_count:
            supporting.append(
                _ev(
                    "support",
                    "day_night",
                    "day_night",
                    features.day_night or "mixed",
                    "day/night pattern",
                    f"{features.day_count} day and {features.night_count} night detections in the current window.",
                )
            )
        if industrial_known and features.nearest_industrial_distance is not None and not near_industry:
            counter.append(
                _ev(
                    "counter",
                    "far_industry",
                    "industrial_facility_distance",
                    _fmt_m(features.nearest_industrial_distance),
                    "weakens industrial association",
                    "Nearest mapped industrial facility is beyond the 1 km spatial-association window.",
                )
            )
        if features.intensity_trend == "increasing" and near_industry and not (repeated_in_window and high_stability):
            supporting.append(
                _ev(
                    "support",
                    "trend",
                    "intensity_trend",
                    "increasing",
                    "candidate short-event signal",
                    "FRP trend is increasing. This is not confirmation of an incident.",
                )
            )
        if short_event:
            counter.append(
                _ev(
                    "counter",
                    "short_duration",
                    "observed_duration_hours",
                    f"{span_h:.1f}",
                    "short temporal duration",
                    "The observed cluster is short-lived in the current window. Repeated detections are not proof of an abnormal fire.",
                )
            )

        scores = {
            LABEL_PERSISTENT: 0.0,
            LABEL_ABNORMAL: 0.0,
            LABEL_VEGETATION: 0.0,
            LABEL_AGRICULTURE: 0.0,
            LABEL_OTHER: 0.12,
            LABEL_INSUFFICIENT: 0.18,
        }

        if sparse:
            scores[LABEL_INSUFFICIENT] += 0.45
            review_reasons.append("low observation count")
        if sparse and (industrial_missing or missing_thermal):
            scores[LABEL_INSUFFICIENT] += 0.35
        if industrial_missing and not veg_land and not crop_land:
            scores[LABEL_INSUFFICIENT] += 0.3

        # Industrial classes require available mapped context. not_found / not_available ≠ no industry.
        if near_industry and high_stability and repeated_in_window:
            scores[LABEL_PERSISTENT] += 0.55
            if historical:
                scores[LABEL_PERSISTENT] += 0.3
            else:
                scores[LABEL_PERSISTENT] += 0.08
            if very_near_industry and night_heavy:
                scores[LABEL_PERSISTENT] += 0.12
            if industrial_land:
                scores[LABEL_PERSISTENT] += 0.08
        if near_industry and short_event and (features.intensity_trend == "increasing" or (features.frp or 0) >= 20):
            scores[LABEL_ABNORMAL] += 0.65
        if near_industry and not repeated_in_window and features.observation_count >= 3 and features.active_days <= 3:
            scores[LABEL_ABNORMAL] += 0.28
        if near_industry and high_stability and repeated_in_window:
            scores[LABEL_ABNORMAL] -= 0.4

        if veg_land and not near_industry:
            scores[LABEL_VEGETATION] += 0.62
        if veg_land and low_stability:
            scores[LABEL_VEGETATION] += 0.18
        if veg_land and short_event:
            scores[LABEL_VEGETATION] += 0.08
        if near_industry and high_stability:
            scores[LABEL_VEGETATION] -= 0.45

        if crop_land and day_heavy:
            scores[LABEL_AGRICULTURE] += 0.68
        if crop_land and short_event:
            scores[LABEL_AGRICULTURE] += 0.12
        if night_heavy and not crop_land:
            scores[LABEL_AGRICULTURE] -= 0.2
        if near_industry and high_stability:
            scores[LABEL_AGRICULTURE] -= 0.4

        if not industrial_known:
            scores[LABEL_PERSISTENT] = 0.0
            scores[LABEL_ABNORMAL] = 0.0

        conflict = near_industry and (veg_land or crop_land) and not (repeated_in_window and high_stability)
        if conflict:
            scores[LABEL_OTHER] += 0.5
            scores[LABEL_ABNORMAL] *= 0.4
            review_reasons.append("conflicting evidence")
            counter.append(
                _ev(
                    "counter",
                    "conflict",
                    "land_context",
                    features.land_context or "mixed",
                    "conflicting contextual signals",
                    "Industrial proximity and land-context class point in different directions. The engine does not invent a single physical cause.",
                )
            )

        label = max(scores, key=scores.get)
        raw = max(0.0, min(1.0, scores[label]))
        runner_up = sorted(scores.values(), reverse=True)[1]
        margin = raw - runner_up
        if label != LABEL_INSUFFICIENT and (margin < 0.12 or raw < 0.38):
            if sparse or industrial_missing or missing_thermal:
                label = LABEL_INSUFFICIENT
                raw = max(raw, 0.35)

        if label in {LABEL_PERSISTENT, LABEL_ABNORMAL} and not industrial_known:
            label = LABEL_INSUFFICIENT
            raw = 0.4
            review_reasons.append("industrial class blocked without context")

        if label == LABEL_INSUFFICIENT:
            band = "UNRESOLVED"
        elif missing_thermal or industrial_missing or margin < 0.12 or (label == LABEL_PERSISTENT and not historical):
            band = "LOW" if label != LABEL_INSUFFICIENT else "UNRESOLVED"
            if label == LABEL_PERSISTENT and not historical:
                band = "MEDIUM" if raw >= 0.55 and margin >= 0.15 else "LOW"
        elif raw >= 0.75 and margin >= 0.2:
            band = "HIGH"
        else:
            band = "MEDIUM"

        if label == LABEL_ABNORMAL:
            priority = "High"
        elif label == LABEL_INSUFFICIENT or band in {"LOW", "UNRESOLVED"}:
            priority = "Medium" if near_industry else "Low"
            if band == "UNRESOLVED":
                review_reasons.append("low confidence")
        elif label == LABEL_PERSISTENT and features.intensity_trend == "increasing":
            priority = "Medium"
        else:
            priority = "Low"

        if label == LABEL_ABNORMAL:
            review_reasons.append("potential abnormal event")
            review_recommended = True
        else:
            review_recommended = band in {"LOW", "UNRESOLVED"} or "conflicting evidence" in review_reasons or "missing context" in review_reasons

        why_not = {
            "wildfire": _why_not_wildfire(features, near_industry, high_stability, veg_land, industrial_missing),
            "agricultural_burning": _why_not_ag(features, near_industry, high_stability, crop_land, day_heavy),
            "industrial_source": _why_not_industrial(features, near_industry, industrial_missing, industrial_not_found, repeated_in_window),
        }

        return ClassificationResult(
            cluster_id=features.cluster_id,
            label=label,
            confidence_band=band,
            priority=priority,
            internal_score=round(raw, 3),
            classifier_name=self.name,
            classifier_version=self.version,
            supporting_evidence=supporting,
            counter_evidence=counter,
            why_not=why_not,
            review_recommended=review_recommended,
            review_reasons=sorted(set(review_reasons)),
        )


def _why_not_wildfire(f: FeatureVector, near_industry: bool, high_stability: bool, veg_land: bool, industrial_missing: bool) -> str:
    if near_industry and high_stability:
        return "Wildfire classification is weakened because the source repeatedly occurs at a spatially stable industrial location."
    if not veg_land and f.land_context:
        return f"Wildfire classification is weakened because land/context is recorded as {f.land_context}, not wildland vegetation."
    if veg_land:
        return "Wildfire remains plausible from land context; other classes were scored against this evidence rather than ruled out."
    if industrial_missing:
        return "Wildfire cannot be excluded: industrial context is not available and land context is incomplete."
    return "Insufficient wildland evidence is available to support a vegetation-fire reading."


def _why_not_ag(f: FeatureVector, near_industry: bool, high_stability: bool, crop_land: bool, day_heavy: bool) -> str:
    if near_industry and high_stability:
        return "Agricultural burning is weakened because detections are spatially stable at an industrial location."
    if f.night_count > f.day_count and f.night_count >= 3:
        return "Agricultural burning is weakened because detections are night-weighted; many crop-residue burns are day-dominant, though this is not a rule."
    if crop_land and day_heavy:
        return "Agricultural burning remains consistent with cropland context and day-weighted detections."
    if not crop_land and f.land_context:
        return f"Agricultural burning is weakened because land/context is {f.land_context}, not cropland."
    return "Insufficient agricultural-context evidence is available to support crop-residue burning."


def _why_not_industrial(f: FeatureVector, near_industry: bool, industrial_missing: bool, industrial_not_found: bool, repeated_in_window: bool) -> str:
    if industrial_missing:
        return "Industrial classification is withheld because industrial context is not_available or unknown — not because a facility was disproven."
    if industrial_not_found:
        return "Industrial classification is weakened because a context search found no mapped facility nearby. not_found does not mean no facility exists."
    if near_industry and repeated_in_window:
        return "Industrial association is supported by proximity and repeated detections in the current window; this still does not establish that a facility caused the detections."
    if near_industry:
        return "Industrial spatial association exists, but the current window does not establish a persistent industrial process or a confirmed abnormal event."
    if f.nearest_industrial_distance is not None:
        return f"Industrial classification is weakened because the nearest mapped facility is {_fmt_m(f.nearest_industrial_distance)} away."
    return "Industrial classification is not supported by available facility context."


class RandomForestClassifierProvider(ClassifierProvider):
    name = "RandomForestClassifierProvider"
    version = "untrained"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        raise NotImplementedError("No trained Random Forest is connected. Use Evidence Baseline.")


class GradientBoostingClassifierProvider(ClassifierProvider):
    name = "GradientBoostingClassifierProvider"
    version = "untrained"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        raise NotImplementedError("No trained gradient-boosting model is connected. Use Evidence Baseline.")


class RemoteModelProvider(ClassifierProvider):
    name = "RemoteModelProvider"
    version = "unconnected"

    def classify(self, features: FeatureVector) -> ClassificationResult:
        raise NotImplementedError("No remote model endpoint is configured.")
