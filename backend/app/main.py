from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.services.pipeline import STORE

app = FastAPI(
    title="THERMAL // INTELLIGENCE",
    description="Explainable thermal source classification API for SIH26162. FIRMS detections are not ground truth.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "product": "THERMAL // INTELLIGENCE",
        "tagline": "Turn thermal anomalies into explainable geospatial intelligence.",
        "mode": STORE.mode,
        "docs": "/docs",
    }
