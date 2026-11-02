import { useEffect, useMemo, useState } from 'react';
import { Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Info, Moon, Search, Sun, ThermometerSun } from 'lucide-react';
import { api, errorText } from '../lib/api';
import { addDaysIso, money, relativeTime, shortDate, todayIso } from '../lib/format';
import type { AirportRef } from '../lib/types';
import { DestinationPhoto } from './DestinationCard';
import { Loading, Notice, StatusPill } from './ui';

type Day = { date: string; condition: string; icon: string; max_c: number | null; min_c: number | null; precipitation_mm: number | null; precipitation_probability: number | null; snowfall_cm: number | null };
type Item = {
  key: string; city: string; country: string; country_code: string; airport: string | null; themes: string[]; kind: 'current' | 'forecast';
  current: { time: string; temperature_c: number | null; condition: string; icon: string; is_day: boolean | null } | null;
  day: Day; timezone: string | null; utc_offset_seconds: number | null; retrieved_at: string; categories: string[];
  fare: { lowest_price: number; currency: string; data_status: string; observed_at: string; departure_date?: string } | null;
};
type Discover = {
  date: string; provider: string; attribution: string; available: boolean; reason?: string; kind?: 'current' | 'forecast';
  categories: { key: string; label: string; rule: string }[]; items?: Item[];
};

export function WeatherIcon({ icon, night, size = 22 }: { icon: string; night?: boolean; size?: number }) {
  const props = { size, 'aria-hidden': true } as const;
  switch (icon) {
    case 'clear': return night ? <Moon {...props} /> : <Sun {...props} />;
    case 'partly-cloudy': return <CloudSun {...props} />;
    case 'cloudy': return <Cloud {...props} />;
    case 'fog': return <CloudFog {...props} />;
    case 'drizzle': return <CloudDrizzle {...props} />;
    case 'rain': return <CloudRain {...props} />;
    case 'snow': return <CloudSnow {...props} />;
    case 'storm': return <CloudLightning {...props} />;
    default: return <ThermometerSun {...props} />;
  }
}

/** Local clock time at the destination from the provider's UTC offset. */
function localTime(offsetSeconds: number | null) {
  if (offsetSeconds == null) return null;
  const d = new Date(Date.now() + offsetSeconds * 1000);
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
}

const temp = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v)}°`);

export function WeatherDiscovery({ origin, onSearchRoute, onExplore }: {
  origin: AirportRef | null;
  onSearchRoute: (from: string, to: string, dates?: { departure?: string }) => void;
  onExplore: (code: string) => void;
}) {
  const [day, setDay] = useState(todayIso());
  const [category, setCategory] = useState('sunny');
  const [state, setState] = useState<{ loading: boolean; data?: Discover; error?: string }>({ loading: true });
  const [shown, setShown] = useState(8);

  useEffect(() => {
    let live = true;
    setState((s) => ({ loading: true, data: s.data }));
    const q = new URLSearchParams({ date: day, ...(origin ? { origin: origin.code } : {}) });
    api<Discover>(`/api/weather/discover?${q}`)
      .then((data) => { if (live) setState({ loading: false, data }); })
      .catch((err) => { if (live) setState({ loading: false, error: errorText(err) }); });
    return () => { live = false; };
  }, [day, origin?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const data = state.data;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const i of data?.items ?? []) for (const k of i.categories) c[k] = (c[k] ?? 0) + 1;
    return c;
  }, [data]);
  const items = useMemo(() => {
    const list = (data?.items ?? []).filter((i) => i.categories.includes(category));
    // Within a category, warmest first for warm/sunny/beach, coldest first for cool/snow, wettest first for rain.
    const by = (i: Item) => (category === 'cool' || category === 'snow' ? (i.day.max_c ?? 99) : category === 'rainy' ? -(i.day.precipitation_mm ?? 0) : -(i.day.max_c ?? -99));
    return list.sort((a, b) => by(a) - by(b) || a.city.localeCompare(b.city));
  }, [data, category]);
  const rule = data?.categories.find((c) => c.key === category)?.rule;

  return (
    <section className="container section weather-section" aria-labelledby="weather-h">
      <div className="section-head weather-head">
        <div>
          <h2 id="weather-h">Where should you travel right now?</h2>
          <p className="muted small">{data?.kind === 'forecast' ? `Daily forecast for ${shortDate(day)}` : 'Current conditions and today’s forecast'} at {data?.items?.length ?? 'popular'} destinations.</p>
        </div>
        <label className="weather-date">
          <span>Travel day</span>
          <input type="date" value={day} min={todayIso()} max={addDaysIso(15)} onChange={(e) => { if (e.target.value) { setDay(e.target.value); setShown(8); } }} />
        </label>
      </div>
      <div className="weather-chips" role="tablist" aria-label="Weather">
        {(data?.categories ?? []).map((c) => (
          <button key={c.key} role="tab" aria-selected={category === c.key} className={category === c.key ? 'active' : ''} title={c.rule}
            onClick={() => { setCategory(c.key); setShown(8); }}>
            {c.label}<span>{counts[c.key] ?? 0}</span>
          </button>
        ))}
      </div>
      {rule && <p className="muted small weather-rule"><Info size={12} /> {rule}.</p>}

      {state.loading && !data && <Loading label="Loading weather…" />}
      {state.error && <Notice kind="error">Weather is unavailable right now: {state.error}</Notice>}
      {data && !data.available && <Notice kind="warn">{data.reason}</Notice>}
      {data?.available && !items.length && <div className="empty-inline"><Info size={16} /> No destinations match this weather {data.kind === 'forecast' ? 'on that day' : 'today'}. Try another category or day.</div>}

      {items.length > 0 && (
        <div className={`weather-grid ${state.loading ? 'is-refreshing' : ''}`}>
          {items.slice(0, shown).map((i) => {
            const now = i.kind === 'current' && i.current;
            const night = now ? i.current!.is_day === false : false;
            const clock = localTime(i.utc_offset_seconds);
            return (
              <article key={i.key} className="card weather-card">
                <div className="weather-photo">
                  <DestinationPhoto dest={i} />
                  <span className="weather-badge"><WeatherIcon icon={now ? i.current!.icon : i.day.icon} night={night} size={18} />{now ? temp(i.current!.temperature_c) : temp(i.day.max_c)}</span>
                </div>
                <div className="weather-body">
                  <div className="weather-title"><b>{i.city}</b><small>{i.country}{i.airport ? ` · ${i.airport}` : ''}</small></div>
                  <p className="weather-cond">
                    {now ? <>Now: {i.current!.condition}</> : <>{i.day.condition}</>}
                    <small>{now ? 'Today' : shortDate(i.day.date)}: {temp(i.day.max_c)} / {temp(i.day.min_c)}{i.day.precipitation_mm ? ` · ${i.day.precipitation_mm} mm rain` : ''}{i.day.precipitation_probability != null ? ` · ${i.day.precipitation_probability}% chance` : ''}</small>
                  </p>
                  <small className="weather-meta">{clock ? `Local time ${clock} · ` : ''}{data?.provider} · {now ? 'current' : 'forecast'} · updated {relativeTime(i.retrieved_at)}</small>
                  {i.fare
                    ? <div className="weather-fare"><span>Last seen from {origin?.code}: <b>{money(i.fare.lowest_price, i.fare.currency)}</b></span><StatusPill status={i.fare.data_status} /><small>observed {relativeTime(i.fare.observed_at)}</small></div>
                    : origin ? <small className="muted">No fare observed from {origin.code} yet.</small> : null}
                  <button className="btn btn-soft small" onClick={() => (origin && i.airport ? onSearchRoute(origin.code, i.airport, { departure: day }) : i.airport && onExplore(i.airport))} disabled={!i.airport}>
                    <Search size={14} /> {origin ? 'Search flights' : 'Plan a trip here'}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {items.length > shown && <div className="load-more"><button className="btn btn-ghost" onClick={() => setShown((n) => n + 8)}>Show more ({items.length - shown})</button></div>}
      {data?.available && <p className="muted small credits">{data.attribution}. Photos: Wikipedia / Wikimedia Commons, credited on each image.</p>}
    </section>
  );
}
