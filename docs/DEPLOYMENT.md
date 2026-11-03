# Deploying FlyCompare AI (free tier)

| Part | Service | Free plan notes |
|---|---|---|
| Website | **Vercel** | Hobby plan; non-commercial use. Forwards `/api/*` to the API, so the browser sees one domain and the session cookie works without cross-site settings. |
| API | **Render** web service | Sleeps after ~15 idle minutes; the first request then takes up to a minute (the site shows "Waking up the server…"). Blocks SMTP, so email uses Brevo's HTTPS API. |
| Database | **Neon** PostgreSQL | Free plan; tables and migrations are created automatically on start-up. |
| Email | **Brevo** | 300 emails/day free. No domain needed: verify your own address as the sender. |
| Price-alert schedule | **GitHub Actions** | `.github/workflows/price-alerts.yml` wakes the API every 3 hours to check alerts. |

Nothing secret is stored in git: every key below is entered in a provider's dashboard.

## 1. Database: Neon
1. Sign up at neon.tech and create a project (any region close to Render's).
2. Copy the **connection string** (`postgresql://…?sslmode=require`). It is the `DATABASE_URL`; the app accepts it as printed.

## 2. Email: Brevo
1. Sign up at brevo.com.
2. **Senders & IP → Senders → Add a sender** with your email address and confirm the link Brevo emails you.
3. **SMTP & API → API keys → Generate a new API key**. It is the `BREVO_API_KEY`; `EMAIL_FROM` is the sender address you verified.

Messages sent "from" a Gmail address through another service can land in spam: check the spam folder when testing, or use an address on your own domain later.

## 3. API: Render
1. Sign up at render.com with GitHub and allow access to this repository.
2. **New → Blueprint**, pick the repository and the branch to deploy. Render reads `render.yaml`.
3. Fill in the values it asks for:
   - `DATABASE_URL`: Neon connection string
   - `APP_PUBLIC_URL`: the Vercel address (fill in after step 4, e.g. `https://flycompare-ai.vercel.app`)
   - `CORS_ORIGINS`: `["https://<your-vercel-address>"]`
   - `TRAVELPAYOUTS_TOKEN`, `TRAVELPAYOUTS_MARKER`: from your Travelpayouts profile
   - `BREVO_API_KEY`, `EMAIL_FROM`: from step 2
   - `WIKIMEDIA_USER_AGENT`: e.g. `FlyCompareAI/1.0 (you@example.com)`
   `SECRET_KEY` and `ALERTS_CRON_TOKEN` are generated for you.
4. When the deploy is green, open `https://<service>.onrender.com/health`: it should return `{"status":"ok"}`.

If Render gives the service a different address than `flycompare-api.onrender.com`, update both rewrite destinations in `frontend/vercel.json`.

## 4. Website: Vercel
1. Sign up at vercel.com with GitHub and **Add New → Project** → import the repository.
2. Set **Root Directory** to `frontend`. Vercel detects Vite; `frontend/vercel.json` supplies the build settings and the `/api` forwarding.
3. Deploy, then copy the address into Render's `APP_PUBLIC_URL` and `CORS_ORIGINS` (step 3) and let Render redeploy.

## 5. Price-alert schedule: GitHub
Repository → **Settings → Secrets and variables → Actions → New repository secret**:
- `ALERTS_API_URL`: `https://<service>.onrender.com`
- `ALERTS_CRON_TOKEN`: copy the value from Render → Environment

Scheduled workflows run from the default branch, so they start once this code is on `main`. Run it once by hand from the **Actions** tab to check it.

## Check the live site
- Home page loads; search Lahore → Dubai for a date a few weeks ahead; results show **Recent fare** and a booking link.
- Sign in with an emailed code (check spam the first time).
- Create a price alert from the results; it appears under Account → Price alerts and is checked within a few hours.
