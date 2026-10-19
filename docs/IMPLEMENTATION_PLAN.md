# Implementation Plan

## Batch 1 — Foundation (created)
- Repository conventions, environment example, PostgreSQL/Redis Compose services.
- Minimal FastAPI app, typed settings, liveness endpoint, test.
- React/TypeScript/Vite/Tailwind product shell.
- Requirements, architecture, implementation plan, traceability docs.

## Next batches
2. SQLAlchemy session/engine, Alembic migrations, airport/airline references, database tests.
3. Flight-offer contract, provider interface, mock/demo provider, normalization and adapter tests.
4. Validated search API, filtering/sorting, comparison scoring, Redis cache and tests.
5. Authentication, preferences, searches, saved flights, user events and authorization.
6. Dataset licensing/data dictionary, ingestion, cleaning, feature store, EDA, baseline ML, time-aware evaluation, MLflow.
7. Frontend search/results/details/filters/compare connected to real API states.
8. Personalized recommendations, natural-language parser, explainability and optional SHAP/delay model.
9. Real-data analytics and safe demo booking/provider redirect.
10. Dockerfiles, CI, monitoring, security hardening, end-to-end tests, documentation.

Order may change when dependencies or test results justify it; record changes in traceability.

## Batch 2 — Demo search API (added)
- Added validated flight-search request/response schemas.
- Added deterministic mock/demo provider and `POST /api/flights/search`.
- Connected the frontend search form to the API and added clearly labeled simulated result cards.
- Added API tests for demo labels and invalid route validation.
- This is not a live airline integration and does not prove availability or bookability.
