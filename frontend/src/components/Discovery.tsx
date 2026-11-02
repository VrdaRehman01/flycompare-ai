import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Compass, Info, MapPin, Plane, Search } from 'lucide-react';
import type { ExploreFn, SearchRouteFn } from '../App';
import { api, errorText } from '../lib/api';
import { dayMonth } from '../lib/format';
import type { AirportRef, Destination, DestinationPage } from '../lib/types';
import { LazyWorldMap } from './LazyMap';
import { Notice, SegmentedControl } from './ui';
import type { MapDestination } from './WorldMap';

type Scope = 'all' | 'seen' | 'nearby' | 'international';
const SCOPES: { value: Scope; label: string }[] = [
  { value: 'all', label: 'Popular' }, { value: 'seen', label: 'Seen in searches' }, { value: 'nearby', label: 'Nearby' }, { value: 'international', label: 'International' },
];

export const availabilityLabel = (d: Destination) => d.availability.status === 'seen_in_searches'
  ? `${d.availability.direct_seen ? 'Direct offers seen' : 'Connecting offers seen'} · last ${dayMonth(d.availability.last_seen)}`
  : 'Suggestion · availability not checked';

export const toMapDestination = (d: Destination): MapDestination => ({
  code: d.airport, city: d.city, country: d.country, lat: d.lat, lon: d.lon,
  status: d.availability.status === 'seen_in_searches' ? 'seen' : 'suggestion', label: availabilityLabel(d),
});

/** "Explore from <origin>": destinations on an interactive map, driven by the departure airport. */
export function Discovery({ origin, onExplore, onSearchRoute }: { origin: AirportRef | null; onExplore: ExploreFn; onSearchRoute: SearchRouteFn }) {
  const [scope, setScope] = useState<Scope>('all');
  const [data, setData] = useState<DestinationPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    const params = new URLSearchParams({ scope: origin ? scope : 'all', page_size: '12', sort: scope === 'nearby' ? 'distance' : 'popular' });
    if (origin) params.set('origin', origin.code);
    api<DestinationPage>(`/api/destinations?${params}`, { signal: ctrl.signal })
      .then((d) => { setData(d); setSelected(null); })
      .catch((err) => { if ((err as Error).name !== 'AbortError') setError(errorText(err)); });
    return () => ctrl.abort();
  }, [origin?.code, scope]); // eslint-disable-line react-hooks/exhaustive-deps

  const mapDestinations = useMemo(() => (data?.items ?? []).map(toMapDestination), [data]);
  const sel = data?.items.find((d) => d.airport === selected);

  return (
    <section className="container section discovery">
      <div className="section-head">
        <div>
          <h2>{origin ? <>Explore from {origin.city} <span className="muted">· {origin.code}</span></> : 'Explore the world'}</h2>
          <p className="muted small">{origin ? 'Destinations update when you change your departure airport. Routes are only marked as seen when a FlyCompare search returned offers.' : 'Choose a departure airport in the search form to see destinations from your city.'}</p>
        </div>
        {origin && <SegmentedControl label="Destination filter" value={scope} onChange={setScope} options={SCOPES} />}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <div className="discovery-grid">
        <div className="card discovery-map">
          <LazyWorldMap origin={origin} destinations={mapDestinations} selected={selected} onSelect={setSelected} height={430}
            route={origin && sel ? { stops: [origin, { code: sel.airport, city: sel.city, country: sel.country, name: '', lat: sel.lat, lon: sel.lon }] } : null}
            caption={origin ? `Map of destinations from ${origin.city}` : 'World map of popular destinations'} />
        </div>
        <div className="card discovery-list">
          {!data ? <div className="loading-block"><span className="spinner dark" /> Loading destinations…</div> : data.items.length === 0 ? (
            <div className="empty-state compact">
              <Compass size={26} />
              <h3>{scope === 'seen' ? 'No routes seen yet' : 'No destinations here'}</h3>
              <p>{scope === 'seen' ? `Search flights from ${origin?.city} — routes that return offers will appear here.` : 'Try another filter.'}</p>
            </div>
          ) : (
            <ul>
              {data.items.map((d) => {
                const seen = d.availability.status === 'seen_in_searches';
                return (
                  <li key={d.key} className={selected === d.airport ? 'active' : ''} onMouseEnter={() => setSelected(d.airport)}>
                    <button className="discovery-item" onClick={() => onExplore(d.airport)} title={`Set ${d.city} as destination`}>
                      <span className={`dot ${seen ? 'seen' : ''}`}>{seen ? <CheckCircle2 size={14} /> : <MapPin size={14} />}</span>
                      <span className="discovery-text">
                        <b>{d.city}, {d.country}</b>
                        <small>{d.airports.slice(0, 2).map((a) => a.code).join(' · ')}{d.distance_km != null ? ` · ${d.distance_km.toLocaleString()} km` : ''}</small>
                        <small className={seen ? 'seen-text' : 'muted'}>{availabilityLabel(d)}</small>
                      </span>
                    </button>
                    {origin && (
                      <button className="icon-btn" onClick={() => onSearchRoute(origin.code, d.airport)} aria-label={`Search flights ${origin.code} to ${d.airport}`} title="Search flights now"><Search size={15} /></button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          <div className="discovery-foot">
            <span className="muted small"><Info size={12} /> {data?.route_note ?? ''}</span>
            <a className="link-btn small" href="#/destinations">All destinations <ArrowRight size={13} /></a>
          </div>
        </div>
      </div>
      {!origin && <p className="muted small discovery-hint"><Plane size={13} /> Tip: choose “Use my current location” in the From field to start from your nearest airport.</p>}
    </section>
  );
}
