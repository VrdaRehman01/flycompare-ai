import { useEffect, useMemo, useState } from 'react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarRange, Compass, Info, Plane, ShieldCheck, Sparkles, Tag } from 'lucide-react';
import type { SearchRouteFn } from '../App';
import { AirportField } from '../components/AirportField';
import { DestinationPhoto } from '../components/DestinationCard';
import { PopularRoutes } from '../components/PopularRoutes';
import { Loading, Notice, StatusPill } from '../components/ui';
import { AirlineLogo } from '../illustrations';
import { api, errorText } from '../lib/api';
import { nightsBetween } from '../lib/calendar';
import { dayMonth, money, relativeTime, shortDate, todayIso } from '../lib/format';
import type { AirportRef, Deal, DealsResponse, Destination, DestinationPage } from '../lib/types';

const THEMES = ['Beach', 'City', 'Culture', 'Nature', 'Family', 'Business'];

export function dealLabel(d: Deal) {
  return d.kind === 'last_seen' ? 'Last-seen fare' : 'Historical observation';
}

function DealFacts({ d }: { d: Deal }) {
  const nights = d.return_date ? nightsBetween(d.departure_date, d.return_date) : 0;
  return (
    <ul className="deal-facts">
      <li><CalendarRange size={13} /> {shortDate(d.departure_date)}{d.return_date ? (nights ? ` – ${shortDate(d.return_date)} · ${nights} night${nights === 1 ? '' : 's'}` : ' · same-day return') : ' · one way'}</li>
      <li><AirlineLogo name={d.airline} size={18} src={d.airline_logo_url} /> {d.airline} · {d.stops === 0 ? 'direct' : `${d.stops} stop${d.stops > 1 ? 's' : ''}`}</li>
      <li className="muted">{d.cabin} · {d.passengers} adult{d.passengers > 1 ? 's' : ''}</li>
    </ul>
  );
}

function Change({ d }: { d: Deal }) {
  if (!d.change || d.change.absolute === 0) return null;
  const down = d.change.absolute < 0;
  return (
    <span className={`deal-change ${down ? 'down' : 'up'}`} title={`Same route, dates and conditions, seen ${relativeTime(d.change.previous_observed_at)} at ${money(d.change.previous_price, d.currency, 2)}`}>
      {down ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}
      {money(Math.abs(d.change.absolute), d.currency)} {down ? 'lower' : 'higher'} than an earlier search
    </span>
  );
}

function Freshness({ d }: { d: Deal }) {
  return (
    <span className={`deal-fresh ${d.kind}`} title={`${dealLabel(d)}: the lowest fare ${d.provider} returned in a FlyCompare search, not a live price.`}>
      {dealLabel(d)} · {relativeTime(d.observed_at)}
    </span>
  );
}

export function DealsPage({ origin, onOriginChange, onSearchRoute, loading, historyVersion }: { origin: AirportRef | null; onOriginChange: (a: AirportRef | null) => void; onSearchRoute: SearchRouteFn; loading: boolean; historyVersion: number }) {
  const [data, setData] = useState<{ loading: boolean; res?: DealsResponse; error?: string }>({ loading: true });
  const [category, setCategory] = useState('cheapest');
  const [theme, setTheme] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Destination[]>([]);
  const [showRules, setShowRules] = useState(false);

  useEffect(() => {
    let live = true;
    setData((d) => ({ loading: true, res: d.res }));
    api<DealsResponse>(`/api/deals${origin ? `?origin=${origin.code}` : ''}`)
      .then((res) => { if (live) setData({ loading: false, res }); })
      .catch((err) => { if (live) setData({ loading: false, error: errorText(err) }); });
    return () => { live = false; };
  }, [origin?.code, historyVersion]);

  const items = data.res?.items ?? [];
  useEffect(() => {
    if (!origin || data.loading || items.length >= 3) { setSuggestions([]); return; }
    const have = new Set(items.map((i) => i.destination.code));
    api<DestinationPage>(`/api/destinations?origin=${origin.code}&page_size=12&sort=popular`)
      .then((p) => setSuggestions(p.items.filter((d) => !have.has(d.airport)).slice(0, 6))).catch(() => setSuggestions([]));
  }, [origin?.code, data.loading, items.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const counts = useMemo(() => {
    const c: Record<string, number> = { cheapest: items.length };
    for (const i of items) for (const k of i.categories) c[k] = (c[k] ?? 0) + 1;
    return c;
  }, [items]);
  const themeCounts = useMemo(() => Object.fromEntries(THEMES.map((t) => [t, items.filter((i) => i.themes.includes(t)).length])), [items]);
  const shown = useMemo(() => {
    let list = category === 'cheapest' ? items : items.filter((i) => i.categories.includes(category));
    if (theme) list = list.filter((i) => i.themes.includes(theme));
    if (category === 'recent') list = [...list].sort((a, b) => a.age_hours - b.age_hours);
    if (category === 'flexible') list = [...list].sort((a, b) => a.flexibility.cheapest.price - b.flexibility.cheapest.price);
    return list;
  }, [items, category, theme]);
  const currencies = [...new Set(shown.map((i) => `${i.currency}·${i.data_status}`))];
  const spotlight = shown[0];
  const rest = shown.slice(1);
  const rule = data.res?.categories.find((c) => c.key === category)?.rule;

  const search = (d: Deal, flex = false) => {
    const dep = flex ? d.flexibility.cheapest.departure_date : d.departure_date;
    const ret = flex ? d.flexibility.cheapest.return_date : d.return_date;
    onSearchRoute(d.origin.code, d.destination.code, dep >= todayIso() ? { departure: dep, returnDate: ret, tripType: d.trip_type } : { tripType: d.trip_type });
  };

  return (
    <div className="container page deals-page">
      <header className="deals-hero">
        <div>
          <span className="eyebrow-pill"><Tag size={13} /> FARES SEEN IN REAL SEARCHES</span>
          <h1>Flight deals</h1>
          <p>Every price here was returned by a provider in an earlier FlyCompare search, with its age and data source. Nothing is estimated, and nothing is called a discount without a like-for-like comparison.</p>
        </div>
        <div className="origin-chooser"><AirportField label="Departing from" value={origin} onChange={onOriginChange} /></div>
      </header>

      <div className="deal-filters">
        <div className="deal-chips" role="tablist" aria-label="Deal type">
          {(data.res?.categories ?? []).map((c) => (
            <button key={c.key} role="tab" aria-selected={category === c.key} className={`chip ${category === c.key ? 'active' : ''}`} title={c.rule}
              disabled={!counts[c.key] && category !== c.key} onClick={() => setCategory(c.key)}>
              {c.label}<span>{counts[c.key] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="deal-chips collections" aria-label="Destination collections">
          <span className="muted small">Collections</span>
          {THEMES.filter((t) => themeCounts[t]).map((t) => (
            <button key={t} className={`chip soft ${theme === t ? 'active' : ''}`} aria-pressed={theme === t} onClick={() => setTheme(theme === t ? null : t)}>{t}<span>{themeCounts[t]}</span></button>
          ))}
          {!THEMES.some((t) => themeCounts[t]) && <span className="muted small">— none yet</span>}
        </div>
        {rule && <p className="muted small deal-rule"><Info size={12} /> {rule} <button className="link-btn small" onClick={() => setShowRules((v) => !v)} aria-expanded={showRules}>{showRules ? 'Hide' : 'How deals work'}</button></p>}
        {showRules && (
          <div className="card rank-info">
            <b>How FlyCompare deals work</b>
            <p>{data.res?.basis} Fares are grouped only when route, trip type, cabin, passengers, currency and data source all match. "Last-seen fare" means seen within {data.res?.rules.fresh_days} days; older fares are "Historical observation". A price change is shown only against an earlier search for the same dates and conditions. Departed dates are never shown.</p>
          </div>
        )}
      </div>

      {data.error && <Notice kind="error">{data.error}</Notice>}
      {data.loading && !data.res && <Loading label="Loading deals…" />}
      {currencies.length > 1 && <Notice kind="info">These deals are in more than one currency or data source; they are ranked separately and never compared with each other.</Notice>}

      {spotlight && (
        <article className="deal-spotlight card">
          <div className="spot-photo"><DestinationPhoto dest={{ key: spotlight.destination.key ?? spotlight.destination.code, city: spotlight.destination.city, country: spotlight.destination.country ?? '' }} eager /></div>
          <div className="spot-body">
            <div className="spot-top"><Freshness d={spotlight} /><StatusPill status={spotlight.data_status} /></div>
            <div className="spot-route"><b>{spotlight.origin.code}</b><span className="route-line" aria-hidden="true"><Plane size={16} /></span><b>{spotlight.destination.code}</b></div>
            <h2>{spotlight.origin.city} to {spotlight.destination.city}{spotlight.destination.country ? <small>, {spotlight.destination.country}</small> : null}</h2>
            <DealFacts d={spotlight} />
            <Change d={spotlight} />
            {spotlight.flexibility.dates_observed > 1 && <small className="muted">{spotlight.flexibility.dates_observed} departure dates seen · lowest {money(spotlight.flexibility.cheapest.price, spotlight.currency)} on {dayMonth(spotlight.flexibility.cheapest.departure_date)}</small>}
            <div className="spot-foot">
              <div className="spot-price"><small>{spotlight.trip_type === 'round-trip' ? 'Round trip' : 'One way'} total</small><strong>{money(spotlight.price, spotlight.currency)}</strong></div>
              <button className="btn btn-primary" disabled={loading} onClick={() => search(spotlight)}>Check this fare now <ArrowRight size={15} /></button>
            </div>
          </div>
        </article>
      )}

      {rest.length > 0 && (
        <div className="deal-grid">
          {rest.map((d) => (
            <article key={d.id} className="card deal-tile">
              <div className="deal-tile-photo">
                <DestinationPhoto dest={{ key: d.destination.key ?? d.destination.code, city: d.destination.city, country: d.destination.country ?? '' }} />
                <span className="deal-codes">{d.origin.code}<Plane size={12} />{d.destination.code}</span>
              </div>
              <div className="deal-tile-body">
                <div className="deal-tile-head">
                  <div><b>{d.destination.city}</b><small>{d.destination.country} · from {d.origin.city}</small></div>
                  <div className="deal-tile-price">
                    <strong>{money(category === 'flexible' ? d.flexibility.cheapest.price : d.price, d.currency)}</strong>
                    <small>{d.trip_type === 'round-trip' ? 'round trip' : 'one way'}</small>
                  </div>
                </div>
                {category === 'flexible'
                  ? <p className="deal-flex"><CalendarRange size={13} /> Lowest of {d.flexibility.dates_observed} dates seen: {shortDate(d.flexibility.cheapest.departure_date)}{d.flexibility.cheapest.return_date ? ` – ${dayMonth(d.flexibility.cheapest.return_date)}` : ''}</p>
                  : <DealFacts d={d} />}
                <Change d={d} />
                <div className="deal-tile-foot">
                  <span><Freshness d={d} /> <StatusPill status={d.data_status} /></span>
                  <button className="btn btn-soft small" disabled={loading} onClick={() => search(d, category === 'flexible')}>Search <ArrowRight size={13} /></button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {!data.loading && !shown.length && !data.error && (
        <div className="card empty-state">
          <Sparkles size={28} />
          <h3>{items.length ? 'No deals in this view' : origin ? `No fares seen from ${origin.city} yet` : 'No fares seen yet'}</h3>
          <p>{items.length ? 'Try another deal type or collection.' : 'Deals appear here after flight searches return prices. Search a route to start.'}</p>
          {items.length > 0 && <button className="btn btn-soft" onClick={() => { setCategory('cheapest'); setTheme(null); }}>Show all deals</button>}
        </div>
      )}

      {suggestions.length > 0 && (
        <section className="section-tight">
          <div className="section-head"><h2>Ideas from {origin?.city}</h2><span className="muted small">Indicative suggestions · prices not checked yet</span></div>
          <div className="idea-row">
            {suggestions.map((s) => (
              <button key={s.key} className="card idea" disabled={loading} onClick={() => onSearchRoute(origin!.code, s.airport)}>
                <span className="idea-photo"><DestinationPhoto dest={s} /></span>
                <span className="idea-text"><b>{s.city}</b><small>{s.country} · {s.airport}</small><small className="muted">Search to see prices</small></span>
                <Compass size={16} className="chev" />
              </button>
            ))}
          </div>
        </section>
      )}

      <PopularRoutes onSearchRoute={onSearchRoute} loading={loading} version={historyVersion} />

      <div className="disclaimer"><ShieldCheck size={15} /> Searching uses the deal's dates when they are still ahead, otherwise two weeks from today. Prices change: the search shows what is available now.</div>
    </div>
  );
}
