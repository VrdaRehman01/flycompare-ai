# FlyCompare AI

Flight comparison and travel decision support. Searches real provider offers (Duffel), compares complete itineraries, keeps per-user saved flights and history, and builds insights only from genuine stored searches.

FlyCompare compares offers. It does not sell or issue tickets.

## Stack
- Frontend: React 18, TypeScript, Vite, Recharts, Vitest
- Backend: FastAPI, Pydantic Settings, SQLAlchemy (SQLite locally, PostgreSQL supported)
- Provider: Duffel (test or live token), or a mock provider for development
- ML: optional fare-estimate model from `ml/` (read-only in the API)

## Data sources
- **Airports** — `backend/app/data/airports_global.json`, ~4,000 airports with scheduled passenger service, built from [OurAirports](https://ourairports.com/data/) (public domain) with timezones from [mwgg/Airports](https://github.com/mwgg/Airports) (MIT). Rebuild with `backend/scripts/build_airport_dataset.py` (instructions in the script).
- **Map** — Natural Earth country shapes (public domain, via the `world-atlas` package) rendered with MapLibre GL. No tile service or API key.
- **Destination photos** — the lead image of the city's English Wikipedia article (accepted only when the article's coordinates match the destination), otherwise a matching view found by searching Wikimedia Commons. Only free licences are used (CC0 / CC BY / CC BY-SA / public domain) and every photo is credited with author and licence; when no suitable photo exists the generated skyline illustration is shown. Lookups run on the server, are batched, and are cached in `destination_images` (photos 30 days, "no photo" 7 days; network errors and rate limits are never cached). **Set `WIKIMEDIA_USER_AGENT` with a contact URL or email** — Wikimedia refuses anonymous clients. To fill the cache for all ~1,100 cities ahead of time: `cd backend && python scripts/warm_destination_images.py`.
- **Exchange rates** — ECB reference rates via Frankfurter.

## Features
- **Search** (no account needed): global airport autocomplete by city, airport name, IATA/ICAO code, metro code (LON, NYC) or country, grouped by city; nearest-airport suggestion from the browser location (asked only when the visitor chooses it; coordinates are rounded to ~1 km and never stored); round trip, one way and multi-city (up to 4 flights); calendar date picker; adults, children (with ages 2–17) and lap infants; cabin class. Validation on client and server.
- **Destination discovery**: “Explore from <your airport>” with an interactive world map and 1,100+ destination cities, filterable by region, theme, distance and routes seen in searches. Routes are only marked “seen” when a FlyCompare search returned offers; everything else is labelled a suggestion.
- **Results**: recommended / cheapest / fastest; filters for stops, airlines, price, total journey time, baggage and refundability (when supplied); expandable itineraries; "Clear all". The recommended score is 60% price + 30% total journey time + 10% stops, min–max normalised across the shown results; the breakdown is visible on every card.
- **Details**: every segment, connection airport and layover, cabin, baggage per type, refund and change conditions with fees exactly as supplied. Anything the provider does not supply is shown as "Not provided".
- **Accounts**: register, sign in/out, profile, change email (password required), change password (signs out other devices), preferences, saved flights, favourite destinations, recently viewed, search history, account deletion with confirmation.
- **Insights**: totals, activity over time, top destinations and routes, airlines in returned offers, cabin and traveller mix, travel-date heatmap, returned fares grouped per currency and data source; 7 / 30 / 90 days / all time; "My searches" or anonymous "All searches".
- **Price history**: every Duffel offer price is stored as an observation. A trend is shown only after ≥3 searches of the same trip on ≥2 different days. Demo prices are never stored.
- **Model estimate**: the promoted `ml/models/fare_log_ridge_model.joblib` is shown as a labelled prediction (historical monthly median one-way fare, EUR), only when the route and month are inside its training data.
- **Currency**: prices always show the provider's original amount; an optional display currency adds an approximate conversion using ECB reference rates. Currencies without a reference rate (for example PKR, QAR, AED) are shown in their original form.
- **Themes**: light, dark and system, persisted per browser and optionally in account preferences.

## Data labels
Every offer and stored record carries `data_status`: `live`, `test` (Duffel sandbox; not real prices or bookable) or `demo` (simulated). The UI labels all three. Searches recorded before this release show "Source not recorded".

## Running locally
Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Optional, enables model estimates:
pip install -r ../ml/requirements.txt
uvicorn app.main:app --reload --port 8000   # from backend/; or from the repo root: uvicorn app.main:app --app-dir backend --reload --port 8000
```
On start-up the API creates missing tables and applies versioned migrations (`backend/app/core/migrations.py`). Existing search history is kept; airport codes are backfilled from labels such as "Karachi (KHI)".

Frontend:
```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxies /api to 127.0.0.1:8000
```
Set `FLYCOMPARE_API_TARGET` to proxy to a different backend.

Configuration lives in `.env` (see `.env.example`). Never commit `.env`. The Duffel token and session handling stay on the server; the browser only receives an HttpOnly session cookie.

## Database migrations
Migrations run automatically when the API starts (`backend/app/core/migrations.py`, recorded in `schema_migrations`):
- `0001` links searches to users and backfills airport codes;
- `0002` adds child/infant counts and multi-city legs to searches and connection airports to fare observations.
New tables (`users`, `user_sessions`, `saved_flights`, `favourite_destinations`, `recently_viewed_flights`, `fare_observations`, `destination_images`) are created automatically. Back up `flycompare.db` before upgrading production data.

Run the backend with `--reload` during development so code changes take effect; the frontend shows a banner if the API server is outdated or unreachable.

## Tests
```bash
cd backend && python -m pytest tests -q        # provider is forced to mock; no network calls
cd ml && python -m pytest tests -q             # from the repository root: python -m pytest ml/tests
cd frontend && npm test && npm run build
```

## Security notes
- Passwords: salted scrypt hashes. Sessions: random tokens, stored only as SHA-256 hashes, HttpOnly + SameSite=Lax cookies (Secure outside development).
- State-changing account/auth requests require an `X-Requested-With` header (CSRF protection together with the CORS allow-list).
- Every account endpoint is scoped to the signed-in user; other users' records return 404.
- Rate limits: auth 10/min, search 20/min, lookups 120/min per client (in-process; move to Redis for multi-process deployments).

See `docs/REQUIREMENT_TRACEABILITY.md` for implementation status and known limitations.
