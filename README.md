# THERMAL // INTELLIGENCE — SIH26162

Prototype for **AI-based detection and classification of industrial fires and persistent thermal sources** using NASA FIRMS-like observations, OSM/industrial context, and an explainable evidence engine.

Tagline: *Turn thermal anomalies into explainable geospatial intelligence.*

This is a local, scientifically conservative analyst workstation. It does **not** treat FIRMS hotspots as ground truth, does **not** equate proximity with causation, and does **not** treat persistence as an accident.

## Why SIH26162 needs this

Thermal anomalies from VIIRS/MODIS are useful cues and weak evidence. Industrial flares, furnaces, crop-residue burning, and vegetation fires can look similar from space. A useful system must:

1. Cluster repeated detections into **sources**, not one-off sparks.
2. Enrich with **context** (mapped facilities, land class) while recording **unknown / not found / not available**.
3. Separate **persistent industrial sources** from **abnormal industrial thermal events**.
4. Show **supporting evidence, counter-evidence, confidence bands, and a human review trail**.

## What this prototype does

Pipeline:

`observation → cleaning → spatial clustering → context → features → Evidence Engine → confidence → GIS → analyst review`

The default classifier is a transparent **Evidence Engine** (`EvidenceBaselineClassifier`). Interfaces exist for Random Forest, gradient boosting, and a remote model; they are **not connected** and are not faked.

## Demo mode (default)

If `FIRMS_MAP_KEY` is missing, Overpass fails, or `APP_MODE=demo`, the API runs **DEMO REPLAY MODE**. No live satellite claim is shown.

Demo scenarios (same engine, not hardcoded screens):

1. Persistent refinery thermal source — Jamnagar, Gujarat  
2. Industrial facility with suspicious thermal activity — Visakhapatnam  
3. Natural vegetation fire — Uttarakhand hills  
4. Agricultural burning — Punjab  
5. Uncertain hotspot — Rajasthan (missing FRP/confidence/context)  
6. Conflicting-evidence hotspot — Pune industrial/vegetation fringe  

## Real API mode

Set `APP_MODE=live` and `FIRMS_MAP_KEY`. The backend will try `FirmsDataProvider`. On any failure it **falls back to demo replay**. OSM/Overpass is attempted only in live mode; failures become context status `not_available`, never “no facility exists”.

## Architecture

See [docs/architecture.md](docs/architecture.md), [docs/data-model.md](docs/data-model.md), [docs/classification.md](docs/classification.md), [docs/demo-script.md](docs/demo-script.md).

- Frontend: Next.js + TypeScript + MapLibre GL + Tailwind  
- Backend: FastAPI evidence pipeline  
- Database: optional PostgreSQL (`data/schemas/postgres.sql`). Default run uses **no database server**; state is in-process plus demo fixtures. SQLAlchemy models are included for a later Postgres bind.

## Setup

### Prerequisites

- Python 3.11+  
- Node.js 20+  

### Environment

```bash
cp .env.example .env
```

Required for a local demo: none beyond the defaults. Optional:

| Variable | Purpose |
|---|---|
| `APP_MODE` | `demo` or `live` |
| `FIRMS_MAP_KEY` | NASA FIRMS map key (server-side only) |
| `DATABASE_URL` | SQLite file or `postgresql+psycopg://…` |
| `ANALYST_WRITE_TOKEN` | Protects review + CSV ingest |
| `OVERPASS_URL` | OSM endpoint |
| `NEXT_PUBLIC_API_BASE_URL` | Direct API if not using the Next proxy |
| `NEXT_PUBLIC_MAP_TILE_URL` | Raster basemap |

Never put FIRMS keys in `NEXT_PUBLIC_*`.

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — the analyst dashboard (no marketing page).

### One-command (Windows)

From the repo root, two terminals:

```powershell
cd backend; python -m venv .venv; .\.venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.main:app --port 8000
cd frontend; npm install; npm run dev
```

Or run `.\scripts\dev.ps1` after creating the venv once.

### Tests

```bash
cd backend
pytest
cd ../frontend
npm test
```

### Ingest a FIRMS CSV

Health page or Sources page → choose a `.csv` with at least `latitude`, `longitude`, `acq_date`, `acq_time`. Sample: `data/demo/firms_sample.csv`. Invalid columns are rejected; missing FRP is allowed and recorded.

Write operations require header `X-Analyst-Token` matching `ANALYST_WRITE_TOKEN` (the Next.js proxy injects this; it is not a FIRMS key).

## Authentication

No user login. Analyst name is captured on review actions for the audit trail. Default write token: `dev-review-token` (local only).

## Main API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | Mode strip |
| GET | `/api/health` | Providers, evaluation status |
| GET | `/api/map` | Observations, clusters, facilities |
| GET | `/api/sources` | Filterable source cards |
| GET | `/api/sources/{id}` | Investigation payload |
| GET | `/api/replay/range` | Demo time span |
| GET | `/api/facilities` | Facility intelligence |
| GET | `/api/review` | Queue + audit |
| POST | `/api/review/{id}` | Confirm / reject / reclassify |
| GET | `/api/alerts` | Alert center |
| GET | `/api/analytics` | Distributions; evaluation withheld |
| GET | `/api/compare?ids=` | Multi-source compare |
| POST | `/api/ingest/csv` | FIRMS CSV |
| GET | `/api/export/geojson` | Export |
| GET | `/api/report/{id}` | Investigation report |

## Known limitations

- No labelled validation set; metrics stay **Evaluation not yet performed.**  
- Clustering is greedy and spatial; it is deterministic, not a physical fire-spread model.  
- Demo OSM extract is tiny; live Overpass is rate-limited and may be unavailable.  
- Map tiles are OpenStreetMap (no API key), not tasked satellite imagery.  
- In-memory store resets when the API process restarts unless you add Postgres persistence.  
- Confidence bands are heuristic, not calibrated probabilities.

## Scientific language

The UI prefers *likely*, *possible*, *spatially associated*, *evidence suggests*, *insufficient evidence*. Nearby industry is **not** “the factory caused the fire.”
