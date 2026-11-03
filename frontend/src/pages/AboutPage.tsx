import type { ReactNode } from 'react';
import { BarChart3, BellRing, BrainCircuit, Cloud, Database, ExternalLink, Github, Globe2, KeyRound, Mail, Monitor, Plane, Server, ShieldCheck, TestTube2, Wallet } from 'lucide-react';
import { StatusPill } from '../components/ui';
import { navigate } from '../lib/router';

const REPO = 'https://github.com/VrdaRehman01/flycompare-ai';

/** Portfolio case study: architecture, data sources and the rules that keep the data honest. */
export function AboutPage() {
  return (
    <div className="container page about-page">
      <section className="about-hero">
        <span className="travel-eyebrow"><Monitor size={13} /> CASE STUDY</span>
        <h1>How FlyCompare AI is built</h1>
        <p>A full-stack flight comparison app: real fares, honest labelling, analytics built only from genuine searches, emailed sign-in codes and price alerts.
          This page explains the architecture and the decisions behind it.</p>
        <div className="about-cta">
          <a className="btn btn-primary" href={REPO} target="_blank" rel="noreferrer noopener"><Github size={16} /> Source on GitHub</a>
          <button className="btn btn-soft" onClick={() => navigate({ page: 'home' })}><Plane size={16} /> Try a search</button>
        </div>
      </section>

      <section className="card about-section">
        <h2>Architecture</h2>
        <div className="arch" role="img" aria-label="Browser to React frontend to FastAPI backend, which uses a database and external data sources">
          <div className="arch-col">
            <ArchBox icon={<Monitor size={18} />} title="React + TypeScript" items={['Vite single-page app', 'Recharts, MapLibre', 'Hash routing, typed API client']} />
          </div>
          <div className="arch-arrow" aria-hidden="true"><span>/api</span></div>
          <div className="arch-col">
            <ArchBox icon={<Server size={18} />} title="FastAPI" strong items={['Search & offer mapping', 'Accounts, email codes, sessions', 'Insights & price history', 'Price-alert checker', 'Guides & trip planner']} />
          </div>
          <div className="arch-arrow" aria-hidden="true"><span>SQL · HTTPS</span></div>
          <div className="arch-col">
            <ArchBox icon={<Database size={18} />} title="Database" items={['SQLite locally, PostgreSQL in production', 'Versioned migrations on start-up']} />
            <ArchBox icon={<Cloud size={18} />} title="External data" items={['Aviasales Data API (fares)', 'Duffel (bookable offers, optional)', 'Open-Meteo, Wikipedia, ECB rates', 'Gmail SMTP (codes & alerts)']} />
          </div>
        </div>
        <p className="muted small">Provider credentials stay on the server. The browser only ever holds an HttpOnly session cookie.</p>
      </section>

      <section className="card about-section">
        <h2>Data honesty rules</h2>
        <p>Every price and record carries its source, and the interface labels it everywhere it appears.</p>
        <div className="label-grid">
          <LabelRow status="live" text="A bookable offer from the provider at search time." />
          <LabelRow status="recent" text="A real fare that Aviasales users found in the last few days. Confirm the price on the booking site." />
          <LabelRow status="test" text="Provider sandbox data, used in development only." />
          <LabelRow status="demo" text="Simulated offers for local development. Refused outside development." />
        </div>
        <ul className="about-list">
          <li>Prices are never invented. If the source has no fare, the app says so.</li>
          <li>A price trend is drawn only after the same trip has been seen in at least 3 searches on 2 different days.</li>
          <li>Different currencies and data sources are never mixed in one statistic.</li>
          <li>Model estimates are labelled as estimates and only shown for routes and months inside the training data.</li>
          <li>Services without a real inventory source (hotels, cars, tours) are switched off rather than shown with fake listings.</li>
        </ul>
      </section>

      <div className="about-grid">
        <Feature icon={<KeyRound size={18} />} title="Sign-in by emailed code">
          Six-digit codes are stored as HMAC hashes. They expire after 10 minutes, work once, allow 5 attempts, have a resend cooldown and an hourly cap.
          Responses never reveal whether an email has an account, and a password registration only creates the account after the address is proven.
        </Feature>
        <Feature icon={<BellRing size={18} />} title="Price alerts">
          A background checker re-searches each alert every few hours and emails once per new low at or below the target.
          On free hosting that sleeps, a scheduled GitHub Action calls a token-protected endpoint instead.
        </Feature>
        <Feature icon={<BarChart3 size={18} />} title="Insights from real searches">
          Activity, top routes, airlines, fares and price trends are computed in SQL from stored searches and fare observations, per user or anonymised across everyone.
        </Feature>
        <Feature icon={<BrainCircuit size={18} />} title="Fare model">
          A log-ridge regression trained on 3.3 million fare observations, validated with monthly expanding-window backtests (about €68 average error versus €88 for a median baseline).
        </Feature>
        <Feature icon={<Wallet size={18} />} title="Local currency">
          Prices default to the visitor's currency from the device timezone, with no location prompt. Conversions use ECB reference rates, with a fallback source for currencies the ECB doesn't publish.
        </Feature>
        <Feature icon={<Globe2 size={18} />} title="Global airports">
          About 4,000 airports from OurAirports with timezones, so arrival times are shown in local time. Search by city, airport, IATA or ICAO code, or metro code.
        </Feature>
      </div>

      <section className="card about-section">
        <h2>Quality</h2>
        <div className="about-stats">
          <Stat icon={<TestTube2 size={18} />} value="190+" label="backend tests (pytest), run offline with stubbed providers" />
          <Stat icon={<TestTube2 size={18} />} value="45" label="frontend unit tests (Vitest)" />
          <Stat icon={<ShieldCheck size={18} />} value="CI" label="GitHub Actions on every push: tests, type-check, build" />
          <Stat icon={<Mail size={18} />} value="0" label="secrets in the repository: configuration lives in .env" />
        </div>
        <div className="stack-chips">
          {['React 18', 'TypeScript', 'Vite', 'Recharts', 'MapLibre GL', 'FastAPI', 'Pydantic', 'SQLAlchemy', 'PostgreSQL', 'scikit-learn', 'pytest', 'Vitest', 'GitHub Actions'].map((t) => <span key={t} className="chip small">{t}</span>)}
        </div>
        <a className="link-btn" href={REPO} target="_blank" rel="noreferrer noopener"><ExternalLink size={13} /> Read the code and README on GitHub</a>
      </section>
    </div>
  );
}

function ArchBox({ icon, title, items, strong }: { icon: ReactNode; title: string; items: string[]; strong?: boolean }) {
  return (
    <div className={`arch-box ${strong ? 'strong' : ''}`}>
      <b>{icon} {title}</b>
      <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

function LabelRow({ status, text }: { status: string; text: string }) {
  return <div className="label-row"><StatusPill status={status} /><span>{text}</span></div>;
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return <article className="card about-feature"><span className="service-icon">{icon}</span><h3>{title}</h3><p>{children}</p></article>;
}

function Stat({ icon, value, label }: { icon: ReactNode; value: string; label: string }) {
  return <div className="about-stat">{icon}<strong>{value}</strong><span>{label}</span></div>;
}
