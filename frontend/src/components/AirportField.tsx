import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Clock3, LocateFixed, MapPin, Plane, Star, X } from 'lucide-react';
import { api } from '../lib/api';
import { rememberAirports, toRef } from '../lib/format';
import type { Airport, AirportRef } from '../lib/types';
import { useDebounced } from './ui';

const RECENT_KEY = 'fc-recent-airports';
const POPULAR = ['DXB', 'LHR', 'IST', 'DOH', 'JFK', 'BKK', 'SIN', 'CDG'];
let popularCache: Promise<Airport[]> | null = null;
const loadPopular = () => (popularCache ??= api<Airport[]>(`/api/airports/lookup?codes=${POPULAR.join(',')}`).catch(() => { popularCache = null; return []; }));

export function readRecentAirports(): AirportRef[] {
  try { return (JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]') as AirportRef[]).filter((a) => /^[A-Z]{3}$/.test(a.code)); } catch { return []; }
}
export function rememberRecentAirport(a: AirportRef) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([a, ...readRecentAirports().filter((x) => x.code !== a.code)].slice(0, 6))); } catch { /* storage blocked */ }
}

export type LocationStatus = { state: 'idle' | 'locating' | 'denied' | 'unavailable' | 'none-nearby' | 'error'; message?: string };

type Item = { kind: 'airport'; airport: AirportRef; section: string; distance?: number } | { kind: 'locate' };

export function AirportField({ label, value, onChange, error, exclude, onUseLocation, locationStatus, autoFocus }: {
  label: string; value: AirportRef | null; onChange: (a: AirportRef | null) => void; error?: string; exclude?: string | null;
  onUseLocation?: () => void; locationStatus?: LocationStatus; autoFocus?: boolean;
}) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Airport[] | null>(null);
  const [popular, setPopular] = useState<Airport[]>([]);
  const [nearby, setNearby] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const debounced = useDebounced(query, 180);

  useEffect(() => { if (editing && !popular.length) void loadPopular().then((p) => { rememberAirports(p); setPopular(p); }); }, [editing, popular.length]);
  useEffect(() => {
    if (!editing || !value?.lat || !value?.lon) { setNearby([]); return; }
    api<Airport[]>(`/api/airports/nearby?lat=${value.lat}&lon=${value.lon}&limit=4`).then((r) => setNearby(r.filter((a) => a.code !== value.code))).catch(() => setNearby([]));
  }, [editing, value?.code, value?.lat, value?.lon]);
  useEffect(() => {
    const q = debounced.trim();
    if (q.length < 2) { setResults(null); setFailed(false); return; }
    const ctrl = new AbortController();
    setLoading(true);
    api<Airport[]>(`/api/airports?q=${encodeURIComponent(q)}&limit=12`, { signal: ctrl.signal })
      .then((r) => { rememberAirports(r); setResults(r); setFailed(false); setActive(0); })
      .catch((err) => { if ((err as Error).name !== 'AbortError') { setResults([]); setFailed(true); } })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [debounced]);
  useEffect(() => {
    if (!editing) return;
    const onDown = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) close(); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [editing]);

  const searching = query.trim().length >= 2;
  const items: Item[] = useMemo(() => {
    const keep = (a: AirportRef) => a.code !== exclude;
    if (searching) return (results ?? []).filter(keep).map((a) => ({ kind: 'airport' as const, airport: toRef(a), section: `${a.city}, ${a.country}` }));
    const list: Item[] = [];
    if (onUseLocation) list.push({ kind: 'locate' });
    nearby.filter(keep).forEach((a) => list.push({ kind: 'airport', airport: toRef(a), section: 'Nearby airports', distance: a.distance_km }));
    readRecentAirports().filter((a) => keep(a) && a.code !== value?.code && !nearby.some((n) => n.code === a.code)).slice(0, 4)
      .forEach((a) => list.push({ kind: 'airport', airport: a, section: 'Recent' }));
    const shown = new Set(list.flatMap((i) => (i.kind === 'airport' ? [i.airport.code] : [])));
    popular.filter((a) => keep(a) && a.code !== value?.code && !shown.has(a.code)).slice(0, 6)
      .forEach((a) => list.push({ kind: 'airport', airport: toRef(a), section: 'Popular destinations' }));
    return list;
  }, [searching, results, nearby, popular, exclude, onUseLocation, value?.code]);

  function open() { setEditing(true); setQuery(''); setActive(0); }
  function close() { setEditing(false); setQuery(''); setResults(null); }
  const choose = (item: Item | undefined) => {
    if (!item) return;
    if (item.kind === 'locate') { onUseLocation?.(); close(); input.current?.blur(); return; }
    onChange(item.airport);
    rememberRecentAirport(item.airport);
    close();
    input.current?.blur();
  };

  const sectionIcon = (s: string) => s === 'Recent' ? <Clock3 size={13} /> : s === 'Popular destinations' ? <Star size={13} /> : s === 'Nearby airports' ? <LocateFixed size={13} /> : <MapPin size={13} />;

  return (
    <div className={`field airport-field ${error ? 'invalid' : ''} ${editing ? 'editing' : ''}`} ref={wrap}>
      <label htmlFor={id}>{label}</label>
      <div className="airport-value">
        <input
          id={id} ref={input} autoFocus={autoFocus} autoComplete="off" spellCheck={false} role="combobox"
          aria-expanded={editing} aria-controls={`${id}-list`} aria-autocomplete="list" aria-invalid={!!error}
          aria-describedby={error ? `${id}-err` : undefined}
          aria-activedescendant={editing && items[active] ? `${id}-i${active}` : undefined}
          placeholder={editing ? 'City, airport, code or country' : 'Select airport'}
          value={editing ? query : value ? `${value.city}, ${value.country} · ${value.code}` : ''}
          onFocus={open}
          onChange={(e) => { setQuery(e.target.value); setActive(0); }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === 'Enter') { e.preventDefault(); choose(items[active]); }
            else if (e.key === 'Escape') { close(); input.current?.blur(); }
            else if (e.key === 'Tab') close();
          }}
        />
        {!editing && value && <small className="airport-name">{value.name}</small>}
        {value && !editing && (
          <button type="button" className="field-clear" aria-label={`Clear ${label}`} onClick={() => { onChange(null); window.setTimeout(() => input.current?.focus(), 0); }}><X size={14} /></button>
        )}
      </div>
      {error && <small className="field-error" id={`${id}-err`}>{error}</small>}
      {!error && locationStatus && locationStatus.state !== 'idle' && locationStatus.message && <small className="field-hint">{locationStatus.message}</small>}
      {editing && (
        <ul className="ac-list card" id={`${id}-list`} role="listbox" aria-label={`${label} suggestions`}>
          {searching && loading && !results?.length && <li className="ac-empty">Searching airports…</li>}
          {searching && !loading && failed && <li className="ac-empty">Airport search is temporarily unavailable. Please try again in a moment.</li>}
          {searching && !loading && !failed && results?.length === 0 && <li className="ac-empty">No airports match “{query}”. Try a city, airport name, country or 3-letter code.</li>}
          {!searching && items.length === 0 && <li className="ac-empty">Type a city, airport, country or code.</li>}
          {items.map((item, i) => {
            const prev = items[i - 1];
            const section = item.kind === 'airport' ? item.section : null;
            const showHeader = section && (!prev || prev.kind !== 'airport' || prev.section !== section);
            return [
              showHeader ? <li key={`h-${section}-${i}`} className="ac-section" role="presentation">{sectionIcon(section!)}{section}</li> : null,
              <li key={item.kind === 'airport' ? `${item.section}-${item.airport.code}` : 'locate'} id={`${id}-i${i}`} role="option" aria-selected={i === active}
                className={`ac-option ${i === active ? 'active' : ''} ${item.kind === 'locate' ? 'locate' : ''}`}
                onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); choose(item); }}>
                {item.kind === 'locate' ? (
                  <><LocateFixed size={16} /><span><b>{locationStatus?.state === 'locating' ? 'Finding your location…' : 'Use my current location'}</b><small>Suggests the nearest commercial airport. Your exact location is not stored.</small></span></>
                ) : (
                  <><Plane size={15} /><span>{searching ? <b>{item.airport.name}</b> : <><b>{item.airport.city}, {item.airport.country}</b><small>{item.airport.name}</small></>}</span>
                    {item.distance != null && <em>{Math.round(item.distance)} km</em>}<code>{item.airport.code}</code></>
                )}
              </li>,
            ];
          })}
        </ul>
      )}
    </div>
  );
}
