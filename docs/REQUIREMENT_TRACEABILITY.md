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


## Update — full functionality batch (2026-10-31)

| Area | Status | Files / verification |
|---|---|---|
| Duffel search, mapping, fare conditions | Implemented and tested | `backend/app/providers/duffel_provider.py`; `tests/test_duffel_mapping.py` (mocked responses) |
| Search validation, provider errors, rate limits | Implemented and tested | `schemas/flight.py`, `core/rate_limit.py`; `tests/test_search_and_history.py` |
| Airport autocomplete | Implemented and tested | `services/airport_service.py`, `data/airports.py`; Duffel Places when configured |
| Accounts, sessions, permissions | Implemented and tested | `core/security.py`, `api/routes/auth.py`, `api/routes/account.py`; `tests/test_auth.py`, `tests/test_permissions.py` |
| Saved flights, favourites, recently viewed, preferences | Implemented and tested | `api/routes/account.py`; `frontend/src/pages/AccountPage.tsx` |
| Per-user search history | Implemented and tested | `services/search_service.py`; anonymous `/api/flights/history` now returns `[]` (privacy) |
| Insights analytics | Implemented and tested | `services/analytics_service.py`, `/api/insights/analytics`; `tests/test_analytics_and_prices.py` |
| Fare observations / price history | Implemented and tested | `models.FareObservation`, `services/price_history_service.py` |
| ML estimate layer | Implemented and tested (read-only) | `services/prediction_service.py`; no model training or promotion performed |
| Currency display | Implemented and tested | `services/currency_service.py`, `frontend/src/lib/currency.ts` |
| Schema migrations | Implemented and tested | `core/migrations.py`; `tests/test_migrations_currency_estimates.py` |
| Frontend filters, ranking, theme, validation | Implemented and tested | `frontend/src/lib/*.test.ts` (Vitest) |

### Known limitations
- Rate limiting and the currency/airport caches are in-process; use Redis for multiple API workers.
- Exchange rates cover ECB currencies only (no PKR, QAR, AED). Unsupported conversions fall back to the original price.
- The fare model covers departure months 2026-09 to 2027-01 and predicts one-way EUR monthly medians; it is not route-date-cabin specific.
- Price trends need repeated searches of the same trip on different days; there is no background collector. Scheduled collection should only be added after confirming Duffel's terms allow it.
- Duffel test-mode prices are sandbox values and are labelled as such everywhere.
- No email verification or password-reset email (no mail service configured).
- No booking: the Select action opens details; booking is out of scope.


## Update — global search, discovery and map (2026-10-31)

Root cause of the “Not Found” errors: the API process on port 8000 had been started without `--reload` before the auth/insights/airport endpoints were added, so it kept serving the old code. Restarting fixed registration, Insights and airport search; the frontend now checks `/api/meta` and shows a banner when the API server is outdated or unreachable.

| Area | Status | Verification |
|---|---|---|
| Global airport search (city, name, IATA/ICAO, metro, country; grouped) | Implemented and tested | `tests/test_global_airports_destinations.py` |
| Nearest airport from browser location | Implemented and tested | backend nearby tests; `frontend/src/lib/search.test.ts` |
| Multi-city, children (ages), lap infants | Implemented and tested | Duffel payload tests; frontend validation tests |
| Destination discovery and route “seen in searches” | Implemented and tested | destination tests |
| Interactive world map (MapLibre + Natural Earth) | Implemented, browser-verified | antimeridian test; end-to-end screenshots |
| Licensed destination photos with attribution | Implemented and tested | image cache and licence tests |
| Anonymous use; browser-local saves synced on sign-in | Implemented, browser-verified | end-to-end run |
| Fare observation history, departure months, route popularity | Implemented and tested | analytics tests |

### Known limitations
- No published airline route database is used, so “direct” routes are only reported when seen in FlyCompare searches.
- Theme tags (Beach, City…) are an editorial list for ~80 popular cities; other destinations can be filtered by region, distance and search only.
- Password reset and email verification are not implemented because no email service is configured.
- Wikimedia rate-limits generic clients; set `WIKIMEDIA_USER_AGENT` with real contact details in production.
