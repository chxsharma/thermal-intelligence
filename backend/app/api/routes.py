from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, UploadFile

from app.classification.engine import LABEL_TITLES
from app.config import get_settings
from app.providers.live import parse_firms_csv
from app.services.pipeline import STORE

router = APIRouter()


def _authorize(token: str | None) -> None:
    expected = get_settings().analyst_write_token
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid analyst write token")


@router.get("/health")
def health() -> dict[str, Any]:
    return STORE.health()


@router.get("/status")
def status() -> dict[str, Any]:
    health = STORE.health()
    return {
        "product": "THERMAL // INTELLIGENCE",
        "mode": health["mode"],
        "classifier": "Evidence Engine",
        "evaluation": "Evaluation not yet performed.",
        "last_firms_ingest_at": health.get("last_firms_ingest_at"),
        "observation_count": health.get("observation_count"),
    }


@router.get("/map")
def map_payload(as_of: str | None = None) -> dict[str, Any]:
    moment = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else None
    snap = STORE.snapshot(moment)
    return {
        "mode": snap["mode"],
        "as_of": snap["as_of"],
        "last_firms_ingest_at": snap.get("last_firms_ingest_at"),
        "metrics": snap["metrics"],
        "observations": [
            {
                "id": o["id"],
                "lat": o["latitude"],
                "lon": o["longitude"],
                "acquired_at": o["acquired_at"],
                "frp": o["frp"],
                "cluster_id": o["cluster_id"],
                "day_night": o["day_night"],
            }
            for o in snap["observations"]
        ],
        "clusters": [
            {
                "id": c["summary"]["id"],
                "lat": c["summary"]["centroid_lat"],
                "lon": c["summary"]["centroid_lon"],
                "label": c["classification"]["label"],
                "title": c["classification_title"],
                "confidence": c["classification"]["confidence_band"],
                "priority": c["classification"]["priority"],
                "persistence_30d": c["summary"]["persistence_30d"],
                "observation_count": c["summary"]["observation_count"],
            }
            for c in snap["clusters"]
        ],
        "facilities": [f.model_dump(mode="json") for f in STORE.facilities],
    }


@router.get("/sources")
def list_sources(
    classification: str | None = None,
    confidence: str | None = None,
    priority: str | None = None,
    review_status: str | None = None,
    industrial_context: str | None = None,
    persistence: str | None = None,
    q: str | None = None,
    sort: str = "priority",
) -> dict[str, Any]:
    cards = STORE.source_cards()
    if classification:
        cards = [c for c in cards if c["classification"] == classification]
    if confidence:
        cards = [c for c in cards if c["confidence"] == confidence]
    if priority:
        cards = [c for c in cards if c["priority"].lower() == priority.lower()]
    if review_status:
        cards = [c for c in cards if c["review_status"] == review_status]
    if industrial_context == "associated":
        cards = [c for c in cards if c["context_status"] == "available" and (c["nearest_facility_m"] or 1e9) <= 1000]
    elif industrial_context == "not_found":
        cards = [c for c in cards if c["context_status"] == "not_found"]
    elif industrial_context == "not_available":
        cards = [c for c in cards if c["context_status"] in {"not_available", "unknown"}]
    if persistence == "persistent":
        cards = [c for c in cards if c["active_days"] >= 14]
    elif persistence == "short":
        cards = [c for c in cards if c["active_days"] <= 3]
    if q:
        needle = q.lower()
        cards = [
            c
            for c in cards
            if needle in c["id"].lower()
            or needle in (c["scenario_name"] or "").lower()
            or needle in (c["region"] or "").lower()
        ]
    rank_priority = {"High": 0, "Medium": 1, "Low": 2}
    rank_conf = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNRESOLVED": 3}
    if sort == "persistence":
        cards.sort(key=lambda c: c["persistence_30d"], reverse=True)
    elif sort == "latest":
        cards.sort(key=lambda c: c["last_observation"], reverse=True)
    elif sort == "confidence":
        cards.sort(key=lambda c: rank_conf.get(c["confidence"], 9))
    else:
        cards.sort(key=lambda c: (rank_priority.get(c["priority"], 9), rank_conf.get(c["confidence"], 9)))
    return {"mode": STORE.mode, "count": len(cards), "sources": cards}


@router.get("/sources/{cluster_id}")
def get_source(cluster_id: str, as_of: str | None = None) -> dict[str, Any]:
    if cluster_id not in STORE.clusters_obs:
        raise HTTPException(status_code=404, detail="Source cluster not found")
    moment = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else STORE.as_of
    doc = STORE._build_cluster(cluster_id, STORE.clusters_obs[cluster_id], moment)
    return {"mode": STORE.mode, **doc, "notes": [n for n in STORE.notes if n["cluster_id"] == cluster_id]}


@router.get("/replay")
def replay(as_of: str = Query(...)) -> dict[str, Any]:
    return map_payload(as_of)


@router.get("/replay/range")
def replay_range() -> dict[str, Any]:
    times = [o.acquired_at for o in STORE.observations]
    return {
        "start": min(times).isoformat(),
        "end": max(times).isoformat(),
        "observation_count": len(times),
    }


@router.get("/facilities")
def facilities() -> dict[str, Any]:
    return {"facilities": [STORE.facility_brief(f.id) for f in STORE.facilities]}


@router.get("/facilities/{facility_id}")
def facility(facility_id: str) -> dict[str, Any]:
    try:
        return STORE.facility_brief(facility_id)
    except StopIteration as exc:
        raise HTTPException(status_code=404, detail="Facility not found") from exc


@router.get("/review")
def review_queue() -> dict[str, Any]:
    queue = []
    for doc in STORE.cluster_docs.values():
        clf = doc["classification"]
        if not clf["review_recommended"]:
            continue
        queue.append(
            {
                "cluster_id": doc["summary"]["id"],
                "classification_title": doc["classification_title"],
                "label": clf["label"],
                "confidence": clf["confidence_band"],
                "priority": clf["priority"],
                "supporting_evidence": clf["supporting_evidence"],
                "counter_evidence": clf["counter_evidence"],
                "persistence_30d": doc["summary"]["persistence_30d"],
                "facility_context": doc["features"]["context_status"],
                "review_reasons": clf["review_reasons"],
                "system_recommendation": doc["classification_title"],
                "final_status": doc["final_status"],
            }
        )
    return {"queue": queue, "history": STORE.reviews}


@router.post("/review/{cluster_id}")
def submit_review(
    cluster_id: str,
    payload: dict[str, Any],
    x_analyst_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(x_analyst_token)
    if cluster_id not in STORE.cluster_docs:
        raise HTTPException(status_code=404, detail="Source cluster not found")
    action = payload.get("action")
    if action not in {"confirm", "reject", "reclassify", "mark_unresolved", "add_note"}:
        raise HTTPException(status_code=400, detail="Unsupported review action")
    new_label = payload.get("new_label")
    if action == "reclassify":
        if new_label not in LABEL_TITLES:
            raise HTTPException(status_code=400, detail="Unknown classification label")
    if action == "mark_unresolved":
        new_label = "insufficient_evidence"
    analyst = str(payload.get("analyst") or "analyst")[:80]
    note = str(payload.get("note") or "")[:4000] or None
    record = STORE.add_review(cluster_id, action, analyst, note, new_label)
    return {"ok": True, "review": record, "source": STORE.cluster_docs[cluster_id]["final_status"]}


@router.get("/alerts")
def alerts() -> dict[str, Any]:
    return {"alerts": STORE.alerts}


@router.get("/analytics")
def analytics() -> dict[str, Any]:
    return STORE.analytics()


@router.get("/compare")
def compare(ids: str) -> dict[str, Any]:
    cluster_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if len(cluster_ids) < 2:
        raise HTTPException(status_code=400, detail="Compare requires at least two source ids")
    missing = [cid for cid in cluster_ids if cid not in STORE.cluster_docs]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown sources: {missing}")
    return {"sources": [STORE.cluster_docs[cid] for cid in cluster_ids]}


def _read_csv_upload(file: UploadFile) -> str:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv FIRMS exports are accepted")
    raw = file.file.read(2_000_000)
    if len(raw) >= 2_000_000:
        raise HTTPException(status_code=400, detail="File exceeds 2 MB validation limit")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8") from exc


def _csv_preview(text: str) -> dict[str, Any]:
    sample = list(csv.reader(io.StringIO(text)))
    header = sample[0] if sample else []
    body = sample[1:]
    header_l = [h.strip().lower() for h in header]
    missing_required = [name for name in ("latitude", "longitude", "acq_date") if name not in header_l]
    parse_error = None
    observations = []
    try:
        observations = parse_firms_csv(text, source="upload")
    except ValueError as exc:
        parse_error = str(exc)
    missing_frp = sum(1 for row in observations if row.frp is None)
    lats = [row.latitude for row in observations]
    lons = [row.longitude for row in observations]
    dates = [row.acquired_at for row in observations]
    valid = not missing_required and parse_error is None and len(observations) > 0
    return {
        "preview": {
            "rows": len(body),
            "columns": header,
            "parsed_observations": len(observations),
            "missing_required_fields": missing_required,
            "missing_frp": missing_frp,
            "date_range": [min(dates).isoformat(), max(dates).isoformat()] if dates else None,
            "geographic_extent": {
                "min_lat": min(lats) if lats else None,
                "max_lat": max(lats) if lats else None,
                "min_lon": min(lons) if lons else None,
                "max_lon": max(lons) if lons else None,
            },
            "validation_status": "valid" if valid else "invalid",
            "parse_error": parse_error,
        },
        "observations": observations,
        "valid": valid,
    }


@router.post("/ingest/csv/preview")
def preview_csv(file: UploadFile, x_analyst_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_analyst_token)
    payload = _csv_preview(_read_csv_upload(file))
    return {"ok": True, "ingested": False, "preview": payload["preview"]}


@router.post("/ingest/csv")
def ingest_csv(file: UploadFile, x_analyst_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_analyst_token)
    payload = _csv_preview(_read_csv_upload(file))
    if not payload["valid"]:
        raise HTTPException(status_code=400, detail=payload["preview"].get("parse_error") or "CSV failed schema validation")
    STORE.reload(extra_observations=payload["observations"])
    return {"ok": True, "ingested": True, "preview": payload["preview"], "mode": STORE.mode}


@router.post("/ingest/firms/refresh")
def refresh_firms(x_analyst_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_analyst_token)
    STORE.reload()
    return {
        "ok": True,
        "mode": STORE.mode,
        "observation_count": len(STORE.observations),
        "last_firms_ingest_at": STORE.last_firms_ok_at.isoformat() if STORE.last_firms_ok_at else None,
        "error": STORE.live_error,
    }


@router.get("/export/geojson")
def export_geojson(ids: str | None = None) -> dict[str, Any]:
    selected = [s.strip() for s in ids.split(",")] if ids else list(STORE.cluster_docs)
    features = []
    for cid in selected:
        if cid not in STORE.cluster_docs:
            continue
        doc = STORE.cluster_docs[cid]
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [doc["summary"]["centroid_lon"], doc["summary"]["centroid_lat"]],
                },
                "properties": {
                    "id": cid,
                    "classification": doc["classification_title"],
                    "confidence": doc["classification"]["confidence_band"],
                    "priority": doc["classification"]["priority"],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


@router.get("/export/csv")
def export_csv(ids: str | None = None) -> dict[str, Any]:
    selected = [s.strip() for s in ids.split(",")] if ids else list(STORE.cluster_docs)
    rows = []
    for cid in selected:
        if cid not in STORE.cluster_docs:
            continue
        card = next(c for c in STORE.source_cards() if c["id"] == cid)
        rows.append(card)
    return {"rows": rows}


@router.get("/report/{cluster_id}")
def report(cluster_id: str) -> dict[str, Any]:
    if cluster_id not in STORE.cluster_docs:
        raise HTTPException(status_code=404, detail="Source cluster not found")
    doc = STORE.cluster_docs[cluster_id]
    return {
        "title": f"Investigation report {cluster_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": STORE.mode,
        "disclaimer": "Evidence suggests possible associations. FIRMS detections are not ground truth. Nearby facilities are not established causes.",
        "source": doc["summary"],
        "classification": doc["classification_title"],
        "confidence": doc["classification"]["confidence_band"],
        "supporting_evidence": doc["classification"]["supporting_evidence"],
        "counter_evidence": doc["classification"]["counter_evidence"],
        "temporal_history": {
            "first_seen": doc["summary"]["first_seen"],
            "last_seen": doc["summary"]["last_seen"],
            "active_days": doc["summary"]["active_days"],
            "persistence": {
                "7d": doc["summary"]["persistence_7d"],
                "14d": doc["summary"]["persistence_14d"],
                "30d": doc["summary"]["persistence_30d"],
                "90d": doc["summary"]["persistence_90d"],
            },
        },
        "industrial_context": {
            "status": doc["features"]["context_status"],
            "nearest_m": doc["features"]["nearest_industrial_distance"],
            "count_1km": doc["features"]["industrial_count_1km"],
            "count_2km": doc["features"]["industrial_count_2km"],
            "facilities": doc["nearby_facilities"],
        },
        "provenance": doc["lineage"]["provenance"],
        "analyst_notes": [n for n in STORE.notes if n["cluster_id"] == cluster_id],
        "review_decision": doc["review"],
    }


@router.get("/labels")
def labels() -> dict[str, str]:
    return LABEL_TITLES
