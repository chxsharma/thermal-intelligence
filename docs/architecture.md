# Architecture

THERMAL // INTELLIGENCE is a local analyst workstation: FastAPI owns science (cluster, features, evidence), Next.js owns GIS interaction.

```
FIRMS CSV / Demo JSON / optional FIRMS API
        │
        ▼
  DataProvider (DemoDataProvider | FirmsDataProvider)
        │
        ▼
  Spatial clustering (deterministic greedy)
        │
        ▼
  ContextProvider (DemoContextProvider | OSMContextProvider)
        │
        ▼
  Feature engineering (features-1.0)
        │
        ▼
  ClassifierProvider → EvidenceBaselineClassifier
        │
        ▼
  REST API  →  Next.js (MapLibre, investigation, review, replay)
```

## Process boundaries

- Browser never receives `FIRMS_MAP_KEY`.
- Review and CSV ingest require `X-Analyst-Token`. The Next.js `/api/intel/*` proxy attaches the server-side token so the key is not a satellite credential in client JS.
- If live providers fail, `IntelligenceStore.reload` keeps serving demo fixtures and labels the mode **DEMO REPLAY MODE**.

## Module map

| Path | Role |
|---|---|
| `backend/app/providers` | Replaceable I/O |
| `backend/app/clustering` | Source identity over time |
| `backend/app/features` | Feature vector |
| `backend/app/classification` | Evidence Engine + unused ML stubs |
| `backend/app/provenance` | Lineage graph |
| `backend/app/services/pipeline.py` | In-memory intelligence store |
| `frontend/features/map` | Map + overview workspace |
| `frontend/features/investigation` | Why / why-not panel |
| `frontend/features/sources` | Explorer / filters |

## Persistence

Default: no database server. Optional Postgres DDL lives in `data/schemas/postgres.sql`. SQLAlchemy ORM sketches are in `backend/app/models/orm.py` for a later bind; the running prototype does not require it.

## Replay

`GET /api/map?as_of=` rebuilds clusters and features using only observations at or before that instant, through the **same** classifier.
