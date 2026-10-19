# Architecture

Target flow: React/TypeScript browser → FastAPI → application services → provider adapters → normalized FlightOffer. PostgreSQL stores durable application data; Redis caches eligible repeated searches. Historical/public data feeds a separate ingestion and ML training pipeline. ML outputs are estimates, never guaranteed future fares.

Trust boundaries: validate browser input server-side; validate/normalize external provider responses; keep secrets server-side; demo booking is not ticket issuance and never processes payment cards.

Current batch only provides API liveness/configuration, a frontend shell, local PostgreSQL/Redis services, and documentation. Search, DB models, providers, and ML are not operational yet.
