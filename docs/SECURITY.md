# Security report — FlyCompare AI

Review date: 3 November 2026 · Scope: this repository, tested locally only (no testing against any deployed system).
No application can be guaranteed impossible to hack; this records the controls in place, what was tested, and what remains.

## What was tested

| Check | Tool / method | Result |
|---|---|---|
| Python static analysis | Bandit 1.9 (`bandit -r backend/app`) | **No issues.** One high (SHA-1 used for an ID, not security) fixed by switching to SHA-256; three lows reviewed and annotated as not security-relevant. |
| Python dependencies | pip-audit 2.10 (runtime and dev requirements) | **No known vulnerabilities.** pytest 8.4.2 (PYSEC-2026-1845) upgraded to 9.x and moved to `requirements-dev.txt`, so production does not install test tools. |
| Frontend dependencies | `npm audit` | **0 vulnerabilities** (production and dev). |
| Secrets in git | Full-history search for `.env`, databases, keys and token patterns | **None committed**, ever. Real keys live only in untracked `.env` files. |
| Unsafe HTML / XSS sinks | Code search for `dangerouslySetInnerHTML`, `innerHTML`, `eval` | One `innerHTML` (map label) already escapes its text. React escapes everything else. |
| Content Security Policy | Production build served with the real headers, six pages loaded in Edge, console checked | **0 violations** after allowing Wikimedia's thumbnail host. |
| Access control / IDOR | Automated tests (pytest, ~210 tests) | Other users' saved flights, routes, alerts, history and favourites return 404 or empty; anonymous users get 401. |
| Authentication | Automated tests | Codes: wrong, expired, reused, superseded, too many attempts, resend cooldown, hourly cap, enumeration-safe responses, email failure reported. Passwords: Argon2id, legacy scrypt upgrade, session invalidation on logout and password change. |
| CSRF, body size, headers, docs, diagnostics | Automated tests | See "Fixed" below. |
| Semgrep, OWASP ZAP | **Not run.** Semgrep has no native Windows build and ZAP is not installed here. | Run both from Linux/WSL or CI before a commercial launch (see checklist). |

## Fixed in this review

1. **Debug mode and API docs in production.** `debug`, `/docs`, `/redoc` and `/openapi.json` are now enabled only in development, regardless of `APP_DEBUG`.
2. **Configuration disclosure.** `/api/flights/provider` (diagnostics) returns 404 outside development.
3. **Security headers.** API: `nosniff`, `X-Frame-Options: DENY`, `frame-ancestors 'none'` CSP, referrer and permissions policies, HSTS in production. Website (`frontend/vercel.json`): a strict CSP (`script-src 'self'`, images only from listed hosts, no framing, `object-src 'none'`), plus the same headers. A test keeps the Vercel and local-preview header sets identical.
4. **Request size limit.** Bodies over 512 KB are refused (413) before being read.
5. **CSRF.** Flight search and the trip planner now require the request-verification header, like every other state-changing route.
6. **Search abuse backstop.** A global ceiling (120 searches/minute across all visitors) protects the fare provider's quota even if a client rotates or spoofs its address.
7. **Unvalidated provider links.** Booking links are accepted only as paths on the booking site (blocks `//evil.example` and `@evil.example` redirects). In the browser, every provider- or Wikipedia-supplied link goes through `safeUrl`, which only allows `http(s)` (blocks `javascript:` and `data:`).
8. **Email HTML.** Links placed in alert emails are restricted to `http(s)` and HTML-escaped.
9. **Password hashing.** New passwords use **Argon2id** (OWASP parameters: 19 MiB, 2 iterations, 1 lane). Older scrypt hashes still verify and are upgraded at the next sign-in.
10. **Unbounded favourites.** Capped at 200 per account (saved flights, routes, alerts and history already had caps).
11. **Abuse visibility.** Every rate-limit hit is logged (`kind:client`, no personal data).
12. **Bug caught by tests:** a variable in the alert email shadowed the HTML-escaping module and would have broken alert emails.

## Controls already in place (verified)

- **Database:** SQLAlchemy ORM and bound parameters throughout; no string-built SQL with user input. Credentials only in server environment variables; the browser never talks to the database.
- **Sessions:** random 256-bit tokens, stored only as SHA-256 hashes; `HttpOnly`, `SameSite=Lax`, `Secure` outside development; a new token on every sign-in (no session fixation); logout and password change revoke sessions server-side.
- **Codes:** 6 digits from `secrets`, stored as HMAC-SHA256 with `SECRET_KEY`, 10-minute expiry, single use, newest-only, 5 attempts, 60 s resend cooldown, 5 per address per hour, per-IP limits, identical responses for registered and unknown emails; a registration never overwrites an existing account's password. The API refuses to start in production with the development `SECRET_KEY`.
- **Authorisation:** every account route derives the user from the session (never from a client-supplied ID); other users' records are reported as not found.
- **Validation:** strict Pydantic schemas on every input (no mass assignment); airport codes, dates, passenger counts and prices are range-checked on the server.
- **Secrets:** never logged (email bodies with codes are not logged; failures log only the error class); `.env` files are git-ignored; `.env.example` holds placeholders only.
- **Third parties:** all provider calls are server-side with timeouts; results are cached (fares 15 min, rates 6 h, photos up to 14 days); there is no endpoint that fetches a user-supplied URL (no SSRF surface).
- **Honest failure:** provider and email failures return clear errors, never fake results or fake "sent" messages.

## Remaining risks and trade-offs

| Item | Why it remains | Mitigation / next step |
|---|---|---|
| Rate limits are per process and keyed by client IP from `X-Forwarded-For` | Behind Vercel and Render the visitor's IP only arrives in that header, which a client calling the API directly could spoof. | Per-email code limits, the global search ceiling and short caching cap the damage. For a commercial launch: a shared store (Redis) and an edge rate limiter or WAF. |
| `style-src 'unsafe-inline'` in the CSP | React `style` attributes (layout values, chart colours) require it. Scripts remain `'self'` only. | Acceptable; inline styles cannot run code. |
| Passwords accepted at 8+ characters with a letter and a digit | No breached-password check. | Add a k-anonymity check (Have I Been Pwned range API) before launch. |
| The app's database role can create tables | Migrations run at start-up with the same connection. | Production: run migrations with an owner role, then run the app with a role limited to SELECT/INSERT/UPDATE/DELETE. |
| No PostgreSQL row-level security | Ownership is enforced in the application layer and covered by tests. | Optional defence-in-depth later; it needs per-request database roles. |
| No central monitoring or alerting | Logs go to the host's log viewer only. | Add error tracking (e.g. Sentry free tier) and a log alert on rate-limit and 5xx spikes. |
| Credentials pasted into a chat during development | The Gmail App Password and Travelpayouts token were shared in a conversation. | **Rotate both before production** (see below) and use the new values only in the host's dashboard. |

## Configured outside the code (deployment checklist)

- [ ] `APP_ENV=production`, a generated `SECRET_KEY` (Render generates one), `APP_DEBUG=false`.
- [ ] HTTPS only: Vercel and Render serve HTTPS; HSTS is sent by both.
- [ ] `CORS_ORIGINS` set to the exact site address only.
- [ ] Database: Neon connection string with `sslmode=require`; separate dev and prod databases; never share the prod URL.
- [ ] Backups: Neon keeps a point-in-time restore history (length depends on the plan). Also take a periodic `pg_dump` and **test restoring it** into a scratch database.
- [ ] Rotate the Gmail App Password (Google account → App passwords → delete and create) and regenerate the Travelpayouts token, and put only the new values in Render.
- [ ] Run Semgrep and an OWASP ZAP baseline scan against a local or staging copy (not production) and fix any high findings.
- [ ] Turn on GitHub Dependabot alerts for the repository.

## Incident response

- **Leaked API key or password:** revoke it at the provider, create a new one, update it in Render's Environment tab (Render redeploys), then check the provider's usage page for misuse.
- **Leaked `SECRET_KEY`:** set a new value in Render. Outstanding sign-in codes stop working; users simply request a new one.
- **Compromised sessions:** delete rows from `user_sessions` (all, or one user's) to sign everyone or that user out.
- **Data loss or corruption:** restore from Neon's point-in-time history or the latest tested `pg_dump`.
- **Suspicious activity:** search the Render logs for `Rate limit reached` and 4xx/5xx spikes; block abusive addresses at the edge.
