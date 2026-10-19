# FlyCompare AI

Intelligent flight comparison, historical price estimation, and travel decision support. This is the first foundation batch, not a finished application. Search, providers, database models, and ML will be implemented in later batches.

## Stack
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI, Pydantic Settings, SQLAlchemy
- Data/cache: PostgreSQL and Redis
- Planned: provider adapters, historical-data ML, MLflow, SHAP, Prometheus/Grafana

## Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Visit http://127.0.0.1:8000/docs and /health.

## Frontend
```bash
cd frontend
npm install
npm run dev
```

## Local PostgreSQL and Redis
From repository root: `docker compose up -d postgres redis`. Copy `.env.example` to `.env` for local configuration. Never commit `.env`.

See `docs/REQUIREMENT_TRACEABILITY.md` for honest implementation status.
