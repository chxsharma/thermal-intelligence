from app.services.pipeline import STORE


def test_demo_scenarios_run_through_same_engine():
    names = {(doc["scenario"] or {}).get("name") for doc in STORE.cluster_docs.values() if doc.get("scenario")}
    assert "Persistent refinery thermal source" in names
    assert "Industrial facility with suspicious thermal activity" in names
    assert "Natural vegetation fire" in names
    assert "Agricultural burning" in names
    assert "Uncertain hotspot" in names
    assert "Conflicting-evidence hotspot" in names


def test_refinery_is_persistent_not_abnormal():
    docs = [d for d in STORE.cluster_docs.values() if (d.get("scenario") or {}).get("id") == "scenario-refinery-persistent"]
    assert docs
    # Clustering groups temporally related detections, not a 90-day persistence object.
    # Persistence remains a classification of a cluster after features are built.
    assert all(d["summary"]["observation_count"] < 10 for d in docs)
    assert max(d["summary"]["observation_count"] for d in docs) >= 2


def test_uncertain_is_unresolved():
    docs = [d for d in STORE.cluster_docs.values() if (d.get("scenario") or {}).get("id") == "scenario-uncertain-hotspot"]
    assert docs
    assert docs[0]["classification"]["label"] == "insufficient_evidence"
    assert docs[0]["classification"]["confidence_band"] == "UNRESOLVED"


def test_health_evaluation_not_fabricated():
    health = STORE.health()
    assert health["evaluation_status"] == "Evaluation not yet performed."
    assert health["mode"] == "DEMO REPLAY MODE"
