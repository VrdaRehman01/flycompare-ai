# Requirement Traceability

Statuses: `Not started`, `In progress`, `Implemented, unverified`, `Implemented and tested`, `Blocked by external dependency`.

| Requirement | Current status | Files / verification |
|---|---|---|
| REQ-001 product decision support | In progress | `frontend/src/App.tsx`; search UI and demo result flow exist |
| REQ-002–005 truthful data status/licensing | In progress | `backend/app/providers/mock_provider.py`, `backend/app/schemas/flight.py`; demo labels included, source licensing work remains |
| REQ-010 basic search contract | Implemented, unverified | `backend/app/api/routes/flights.py`, `backend/app/schemas/flight.py`; `backend/tests/test_flight_search.py` |
| REQ-011–015 provider normalization and real provider | In progress | Demo provider exists; multi-provider normalization/live test integration pending |
| REQ-016 filtering/comparison | Not started | Planned comparison service and tests |
| REQ-017 Redis search caching | Not started | Planned provider-aware bounded TTL cache |
| REQ-020 API framework/configuration | In progress | `backend/app/main.py`, `backend/app/core/config.py`; SQLAlchemy database integration pending |
| REQ-021 endpoint coverage | In progress | Demo search endpoint exists; remaining endpoints pending |
| REQ-022–025 persistence/security | Not started | Planned database models, migrations, auth, authorization, and tests |
| REQ-030–034 comparison/recommendation/AI | Not started | Planned comparison and recommendation services |
| REQ-040–048 ML/data/MLflow/SHAP | Not started | Planned `data/`, `ml/`, `backend/app/ml/` |
| REQ-050–052 pages/analytics/UX | In progress | Search UI exists; remaining pages and analytics pending |
| REQ-060 safe demo booking | Not started | Planned booking service and tests |
| REQ-061–064 operations/security/CI | In progress | Compose services exist; monitoring/CI/security hardening pending |
| REQ-070–074 tests/success criteria | In progress | Health and demo-search tests added; full suite and second provider pending |
