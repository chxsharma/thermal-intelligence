from fastapi.testclient import TestClient

from app.main import app
from app.services.pipeline import STORE

client = TestClient(app)
HEADERS = {"X-Analyst-Token": "dev-review-token"}


def test_csv_preview_does_not_ingest():
    before = len(STORE.observations)
    csv = b"latitude,longitude,acq_date,acq_time,frp,confidence,bright_ti4,daynight,satellite,instrument\n22.37,69.86,2026-09-01,1812,12.5,n,340.1,N,NOAA-20,VIIRS\n"
    response = client.post("/api/ingest/csv/preview", files={"file": ("sample.csv", csv, "text/csv")}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["ingested"] is False
    assert body["preview"]["validation_status"] == "valid"
    assert body["preview"]["rows"] == 1
    assert "latitude" in [c.lower() for c in body["preview"]["columns"]]
    assert len(STORE.observations) == before


def test_csv_preview_missing_columns():
    csv = b"foo,bar\n1,2\n"
    response = client.post("/api/ingest/csv/preview", files={"file": ("bad.csv", csv, "text/csv")}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["preview"]["validation_status"] == "invalid"
