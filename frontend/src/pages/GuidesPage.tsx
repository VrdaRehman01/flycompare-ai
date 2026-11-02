import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowUpRight, BedDouble, BookOpen, CalendarRange, Clock3, Coins, ExternalLink, Languages, Lightbulb, MapPin, Plane, Search, Sun, Ticket, Users, X } from 'lucide-react';
import type { SearchRouteFn } from '../App';
import { AirportField } from '../components/AirportField';
import { ClimateChart } from '../components/charts';
import { DestinationPhoto } from '../components/DestinationCard';
import { TravelHero } from '../components/TravelUI';
import { EmptyState, Loading, Notice, Price } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useFeatures } from '../lib/features';
import { navigate } from '../lib/router';
import type { Guide, GuideCard } from '../lib/travel';
import type { AirportRef } from '../lib/types';

export function GuidesPage({ location, origin, onSearchRoute }: { location?: string; origin: AirportRef | null; onSearchRoute: SearchRouteFn }) {
  return location ? <GuideDetail location={location} origin={origin} onSearchRoute={onSearchRoute} /> : <GuideList />;
}

function GuideList() {
  const [items, setItems] = useState<GuideCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('All');
  const [cats, setCats] = useState<string[]>([]);
  useEffect(() => {
    api<{ items: GuideCard[]; categories: string[] }>('/api/guides').then((d) => { setItems(d.items); setCats(d.categories); }).catch((err) => setError(errorText(err)));
  }, []);
  const shown = (items ?? []).filter((g) => (category === 'All' || g.top_categories.includes(category))
    && (!q.trim() || `${g.city} ${g.country}`.toLowerCase().includes(q.trim().toLowerCase())));
  return (
    <div className="container page travel-page">
      <TravelHero icon={<BookOpen size={13} />} eyebrow="TRAVEL GUIDES" title="Travel guides"
        subtitle="Where to stay, what to see, the best months to visit from real weather data, and local tips: all linked to stays, tours and a trip plan.">
        <div className="travel-form guides-form">
          <label className="search-input"><Search size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter featured guides" aria-label="Filter guides" />{q && <button onClick={() => setQ('')} aria-label="Clear"><X size={14} /></button>}</label>
          <AirportField label="Or open any city" value={null} onChange={(a) => a && navigate({ page: 'guides', location: a.code })} />
        </div>
      </TravelHero>
      <div className="chip-wrap guide-cats">{['All', ...cats].map((c) => <button key={c} className={`chip ${category === c ? 'active' : ''}`} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}</div>
      {error && <Notice kind="error">{error}</Notice>}
      {!items && !error && <Loading label="Loading guides…" />}
      <div className="dest-grid">
        {shown.map((g) => (
          <article key={g.key} className="card dest-card guide-card">
            <button className="dest-art" onClick={() => navigate({ page: 'guides', location: g.airport })} aria-label={`Read the ${g.city} guide`}><DestinationPhoto dest={g} /></button>
            <div className="dest-info">
              <span><b>{g.city}</b><small>{g.country}</small></span>
              <button className="dest-cta" onClick={() => navigate({ page: 'guides', location: g.airport })}>Read <ArrowUpRight size={14} /></button>
            </div>
            <p className="guide-tagline">{g.tagline}</p>
            <div className="dest-meta"><span className="dest-tags">{g.top_categories.map((t) => <span key={t} className="tag">{t}</span>)}</span><small className="muted">{g.sights} sights</small></div>
          </article>
        ))}
      </div>
      {items && !shown.length && <div className="card"><EmptyState icon={<BookOpen size={28} />} title="No featured guide matches">Use “Open any city” for a basic guide with climate and overview.</EmptyState></div>}
    </div>
  );
}

function GuideDetail({ location, origin, onSearchRoute }: { location: string; origin: AirportRef | null; onSearchRoute: SearchRouteFn }) {
  const [g, setG] = useState<Guide | null>(null);
  const features = useFeatures();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setG(null); setError(null);
    api<Guide>(`/api/guides/detail?location=${encodeURIComponent(location)}`).then(setG).catch((err) => setError(errorText(err)));
  }, [location]);
  if (error) return <div className="container page"><Notice kind="error">{error}</Notice><button className="btn btn-soft" onClick={() => navigate({ page: 'guides' })}><ArrowLeft size={15} /> All guides</button></div>;
  if (!g) return <div className="container page"><Loading label="Loading guide…" /></div>;
  const code = g.airport;
  return (
    <div className="container page travel-page guide-page">
      <button className="link-btn back-link" onClick={() => navigate({ page: 'guides' })}><ArrowLeft size={14} /> All guides</button>
      <section className="card guide-hero">
        <div className="guide-hero-photo"><DestinationPhoto dest={g} eager /></div>
        <div className="guide-hero-copy">
          <span className="travel-eyebrow"><BookOpen size={13} /> TRAVEL GUIDE</span>
          <h1>{g.city}</h1>
          <p className="muted">{g.country}{g.tagline ? ` · ${g.tagline}` : ''}</p>
          <div className="guide-actions">
            <button className="btn btn-primary" onClick={() => navigate({ page: 'planner', location: code })}><CalendarRange size={15} /> Plan a trip</button>
            {features.has('stays') && <button className="btn btn-soft" onClick={() => navigate({ page: 'stays', location: code })}><BedDouble size={15} /> Stays</button>}
            {features.has('tours') && <button className="btn btn-soft" onClick={() => navigate({ page: 'tours', kind: 'group', location: code })}><Users size={15} /> Tours</button>}
            {origin && origin.code !== code && <button className="btn btn-ghost" onClick={() => onSearchRoute(origin.code, code)}><Plane size={15} /> Flights from {origin.code}</button>}
          </div>
        </div>
      </section>

      <div className="guide-grid">
        <div className="guide-main">
          {g.overview && (
            <section className="card panel">
              <h2>Overview</h2>
              <p>{g.overview.extract}</p>
              {g.overview.url && <a className="link-btn small" href={g.overview.url} target="_blank" rel="noreferrer noopener">Read more on Wikipedia <ExternalLink size={12} /></a>}
              <small className="muted block">Summary: {g.overview.source}</small>
            </section>
          )}

          <section className="card panel">
            <h2><Sun size={17} /> Best time to visit</h2>
            {g.climate ? (
              <>
                <p>Most comfortable: <b>{g.climate.best_months.join(', ')}</b>{g.climate.avoid_months.length ? <> · Hardest: <b>{g.climate.avoid_months.join(', ')}</b></> : null}</p>
                <ClimateChart months={g.climate.months} best={g.climate.best_months} />
                <small className="muted">Average daytime highs; green bars are the best months (highs near 24°C and few rainy days). {g.climate.source}. One year of observations, so individual years vary.</small>
              </>
            ) : <p className="muted">Climate data isn't available right now.</p>}
          </section>

          {g.sights.length > 0 && (
            <section className="card panel">
              <h2><Ticket size={17} /> Top things to do</h2>
              <ol className="sight-list">
                {g.sights.map((s) => (
                  <li key={s.name}>
                    <div><b>{s.name}</b><span className="tag">{s.category}</span></div>
                    <p>{s.blurb}</p>
                    <small className="muted"><Clock3 size={11} /> {s.hours} h · best {s.slot === 'any' ? 'any time' : `in the ${s.slot}`} · {s.usd ? <>typically <Price amount={s.usd} currency="USD" inline /></> : 'free to visit'}</small>
                  </li>
                ))}
              </ol>
              <small className="muted">{g.content_note}</small>
            </section>
          )}
          {!g.curated && <Notice>There is no curated guide for {g.city} yet. You can still plan a trip there; the planner leaves free days for you to fill.</Notice>}
        </div>

        <aside className="guide-side">
          <section className="card panel guide-facts">
            <h3>Quick facts</h3>
            {g.language && <p><Languages size={14} /> <span>Language</span><b>{g.language}</b></p>}
            {g.currency && <p><Coins size={14} /> <span>Currency</span><b>{g.currency}</b></p>}
            <p><BedDouble size={14} /> <span>Typical mid-range night</span><b><Price amount={g.typical_hotel_night_usd} currency="USD" inline /></b></p>
            <p><Plane size={14} /> <span>Airports</span><b>{g.airports.map((a) => a.code).join(', ')}</b></p>
          </section>
          {g.areas.length > 0 && (
            <section className="card panel">
              <h3><MapPin size={15} /> Where to stay</h3>
              {g.areas.map((a) => (
                <div key={a.name} className="area-item">
                  <b>{a.name}</b><span className="tag">{a.best_for}</span>
                  <p>{a.blurb}</p>
                </div>
              ))}
              {features.has('stays') && <button className="btn btn-soft full" onClick={() => navigate({ page: 'stays', location: code })}><BedDouble size={15} /> Compare stays in {g.city}</button>}
            </section>
          )}
          {g.tips.length > 0 && (
            <section className="card panel">
              <h3><Lightbulb size={15} /> Local tips</h3>
              <ul className="tip-list">{g.tips.map((t) => <li key={t}>{t}</li>)}</ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
