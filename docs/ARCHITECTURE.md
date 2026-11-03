# Architecture

**Flow:** React/TypeScript browser → FastAPI → services → provider adapters → normalised `FlightOffer`.

- **Frontend** (Vite, Vercel): a single-page app. Vercel serves it and forwards `/api/*` to the backend, so the browser talks to one origin.
- **Backend** (FastAPI, Render): validates every input with Pydantic, applies rate limits and CSRF checks, and calls fare, weather, image and exchange-rate sources server-side. Secrets never reach the browser.
- **Fare provider** (Travelpayouts / Aviasales Data API): recent real fares, labelled `recent`. A round trip with no round-trip fare (or longer than the source's 30-day limit) is priced from two real one-way fares and labelled as two tickets. When exact dates are empty, nearby dates with real fares are suggested. Prices are never invented.
- **Database** (SQLite locally, PostgreSQL on Neon in production): accounts, sessions, saved flights and routes, price alerts, search history and fare observations. Schema changes run as versioned migrations at start-up.
- **Email** (Gmail SMTP locally, Brevo HTTPS API in production): sign-in codes and price-alert emails.
- **Price alerts:** a GitHub Actions schedule calls a token-protected endpoint every three hours.
- **ML** (`ml/`): a weekly workflow refreshes a public fare dataset and retrains a ridge model. Its output is shown only as a labelled historical estimate, never as a live price.

**Trust boundaries:** browser input is validated server-side; provider responses are validated and booking links restricted to the booking site; FlyCompare compares fares and never sells tickets or handles payment cards. See `DEPLOYMENT.md` for hosting.
