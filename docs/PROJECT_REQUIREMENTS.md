# FlyCompare AI — Project Requirements

Source of truth: the user-provided **FlyCompare AI — Complete Project Blueprint**. This is a checklist, not a claim that every feature is already implemented.

## Product and data integrity
- REQ-001: Intelligent travel decision support, not merely a ticket-selling website.
- REQ-002: Label live, test, demo, simulated, historical, reference, and last-updated data accurately.
- REQ-003: Historical/demo data must never imply real-time availability or guaranteed prices.
- REQ-004: No unsupported claims of global inventory or ticket issuance.
- REQ-005: Respect dataset licenses, API terms, and OpenStreetMap usage/attribution.

## Search and provider architecture
- REQ-010: Search by origin, destination, dates, passengers, and cabin.
- REQ-011: Normalize providers to one provider-independent flight-offer schema.
- REQ-012: Mock/historical provider plus legitimate test/live provider when access exists.
- REQ-013: Add providers without changing the frontend contract.
- REQ-014: Normalize route, segments, price/currency, times, duration, stops, baggage and fare rules when available.
- REQ-015: Track provider/source, retrieval time, and data status.
- REQ-016: Filter, sort, inspect, and compare offers.
- REQ-017: Cache eligible repeated searches with safe TTL/invalidation.

## Backend and persistence
- REQ-020: FastAPI, Pydantic, SQLAlchemy, PostgreSQL, HTTPX.
- REQ-021: Airport search, flight search/detail, compare, recommendations, price/delay prediction, preferences, analytics, and demo-booking APIs.
- REQ-022: Persist users, searches, offers, fare details, saved flights, events, predictions as appropriate.
- REQ-023: Migrations, relationships, constraints, indexes, consistent schemas.
- REQ-024: Secure authentication, authorization, validation, rate limiting, environment secrets.
- REQ-025: Never store real payment-card information.

## Comparison, recommendations, AI
- REQ-030: Configurable scoring for price, duration, stops, baggage, flexibility, convenience.
- REQ-031: Cheapest, fastest, fewest stops, best baggage, most flexible, best preference match.
- REQ-032: Explain recommendations and handle missing attributes honestly.
- REQ-033: Optional natural-language parser to validated filters.
- REQ-034: AI must not invent availability, fares, schedules, baggage, or rules.

## Data science and ML
- REQ-040: Licensed historical/public data for EDA, training, trends, and analytics.
- REQ-041: Cleaning, validation, feature engineering, reproducible data pipeline.
- REQ-042: Historical price regression with MAE, RMSE, R².
- REQ-043: Time-aware validation and prevention of leakage.
- REQ-044: Linear baseline and suitable tree models where justified.
- REQ-045: Price ranges/anomalies only with adequate comparable data.
- REQ-046: Optional delay model only with suitable data.
- REQ-047: SHAP where appropriate; MLflow tracking/versioning.
- REQ-048: Consistent training/inference feature schemas.

## UI, analytics, booking, operations
- REQ-050: Home/search, results, details, compare, assistant, analytics, saved flights, trips/demo history, profile/preferences, admin/monitoring.
- REQ-051: Real-data analytics for prices/routes/airlines/duration/stops/preferences/model metrics/API latency/errors.
- REQ-052: Responsive accessible UI with loading, empty, error, retry states.
- REQ-060: Demo booking or provider redirect only; no real payment/ticket issuance.
- REQ-061: Docker reproducibility.
- REQ-062: Prometheus and Grafana.
- REQ-063: Automated tests and CI/CD.
- REQ-064: Structured logs, error handling, timeouts, transactions, privacy-aware retention.

## Tests and success criteria
- REQ-070: Unit tests for scoring and price calculations.
- REQ-071: API/provider/database/frontend/ML-schema tests.
- REQ-072: End-to-end search → compare → save/demo-booking test.
- REQ-073: Add a second provider/mock provider without changing frontend contract.
- REQ-074: Explicit limitations; no fabricated capabilities.
