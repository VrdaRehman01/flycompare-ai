import { useEffect, useMemo, useState } from 'react';
import { Globe2, LayoutGrid, Map as MapIcon, Search, X } from 'lucide-react';
import type { ExploreFn, SearchRouteFn } from '../App';
import { AirportField } from '../components/AirportField';
import { DestinationCard } from '../components/DestinationCard';
import { toMapDestination } from '../components/Discovery';
import { LazyWorldMap } from '../components/LazyMap';
import { Listbox } from '../components/Listbox';
import { EmptyState, Notice, SegmentedControl, useDebounced } from '../components/ui';
import { api, errorText } from '../lib/api';
import type { AirportRef, Destination, DestinationPage, RouteSnapshot } from '../lib/types';
import { useAuth } from '../state';

const THEMES = ['All', 'Beach', 'City', 'Culture', 'Nature', 'Family', 'Business'];
const PAGE = 24;

/** Latest stored lowest fare per route, used by Deals. Never invents prices. */
export function useRouteSnapshots(origin: string | null, codes: string[], version = 0) {
  const [snapshots, setSnapshots] = useState<Record<string, RouteSnapshot>>({});
  const key = codes.join(',');
  useEffect(() => {
    if (!origin) { setSnapshots({}); return; }
    const routes = key.split(',').filter((c) => c && c !== origin).map((c) => `${origin}-${c}`).join(',');
    if (!routes) return;
    api<RouteSnapshot[]>(`/api/prices/routes?routes=${routes}`)
      .then((rows) => setSnapshots(Object.fromEntries(rows.map((r) => [r.destination, r]))))
      .catch(() => setSnapshots({}));
  }, [origin, key, version]);
  return snapshots;
}

export function DestinationsPage({ origin, onOriginChange, onExplore, onSearchRoute, loading }: { origin: AirportRef | null; onOriginChange: (a: AirportRef | null) => void; onExplore: ExploreFn; onSearchRoute: SearchRouteFn; loading: boolean }) {
  const { favourites, toggleFavourite } = useAuth();
  const [q, setQ] = useState('');
  const [region, setRegion] = useState('all');
  const [theme, setTheme] = useState('All');
  const [sort, setSort] = useState<'popular' | 'distance' | 'name'>('popular');
  const [scope, setScope] = useState<'all' | 'seen' | 'nearby' | 'international'>('all');
  const [view, setView] = useState<'grid' | 'map'>('grid');
  const [items, setItems] = useState<Destination[]>([]);
  const [meta, setMeta] = useState<Omit<DestinationPage, 'items'> | null>(null);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useDebounced(q, 250);

  const params = useMemo(() => {
    const p = new URLSearchParams({ sort: sort === 'distance' && !origin ? 'popular' : sort, scope: origin ? scope : 'all', page_size: String(PAGE) });
    if (origin) p.set('origin', origin.code);
    if (query.trim()) p.set('q', query.trim());
    if (region !== 'all') p.set('region', region);
    if (theme !== 'All') p.set('theme', theme);
    return p.toString();
  }, [origin, query, region, theme, sort, scope]);

  useEffect(() => {
    const ctrl = new AbortController();
    setBusy(true);
    setError(null);
    api<DestinationPage>(`/api/destinations?${params}&page=1`, { signal: ctrl.signal })
      .then(({ items: list, ...rest }) => { setItems(list); setMeta(rest); setPage(1); })
      .catch((err) => { if ((err as Error).name !== 'AbortError') setError(errorText(err)); })
      .finally(() => setBusy(false));
    return () => ctrl.abort();
  }, [params]);

  const loadMore = () => {
    setBusy(true);
    api<DestinationPage>(`/api/destinations?${params}&page=${page + 1}`)
      .then((d) => { setItems((all) => [...all, ...d.items]); setPage(page + 1); })
      .catch((err) => setError(errorText(err)))
      .finally(() => setBusy(false));
  };

  const reset = () => { setQ(''); setRegion('all'); setTheme('All'); setScope('all'); setSort('popular'); };
  const filtered = !!(q || region !== 'all' || theme !== 'All' || scope !== 'all');

  return (
    <div className="container page">
      <div className="page-head">
        <div>
          <h1>Explore Destinations</h1>
          <p>{meta ? `${meta.total.toLocaleString()} destinations worldwide` : 'Destinations worldwide'}{origin ? `, measured from ${origin.city} (${origin.code})` : ''}. Pick one to plan your search.</p>
        </div>
        <div className="origin-chooser"><AirportField label="Departing from" value={origin} onChange={onOriginChange} /></div>
      </div>

      <div className="card dest-toolbar">
        <label className="search-input"><Search size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search city, country or airport code" aria-label="Search destinations" />{q && <button onClick={() => setQ('')} aria-label="Clear search"><X size={14} /></button>}</label>
        <Listbox label="Region" icon={<Globe2 size={14} />} value={region} onChange={setRegion} options={[{ value: 'all', label: 'All regions' }, ...(meta?.regions ?? []).filter((r) => r !== 'Antarctica').map((r) => ({ value: r, label: r }))]} />
        <Listbox label="Sort" value={sort} onChange={(v) => setSort(v as typeof sort)} align="right" options={[
          { value: 'popular', label: 'Most popular' }, { value: 'distance', label: 'Nearest first', disabled: !origin, hint: origin ? undefined : 'Choose a departure airport' }, { value: 'name', label: 'A–Z' },
        ]} />
        <SegmentedControl label="View" value={view} onChange={setView} options={[{ value: 'grid', label: 'Grid' }, { value: 'map', label: 'Map' }]} />
      </div>
      <div className="chip-row">
        <div className="chips" role="group" aria-label="Travel theme">{THEMES.map((t) => <button key={t} className={`chip ${theme === t ? 'active' : ''}`} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t}</button>)}</div>
        {origin && <SegmentedControl label="Route filter" value={scope} onChange={setScope} options={[{ value: 'all', label: 'All' }, { value: 'seen', label: 'Seen in searches' }, { value: 'nearby', label: 'Nearby' }, { value: 'international', label: 'International' }]} />}
      </div>
      {theme !== 'All' && meta && <p className="muted small">{meta.themes_note}</p>}
      {error && <Notice kind="error">{error}</Notice>}

      {view === 'map' ? (
        <div className="card map-panel">
          <LazyWorldMap origin={origin} destinations={items.map(toMapDestination)} onSelect={(code) => onExplore(code)} height={560} caption="Destinations map" />
          <p className="muted small map-note">Click a destination to set it in your search. {meta?.route_note}</p>
        </div>
      ) : items.length === 0 && !busy ? (
        <div className="card"><EmptyState icon={<LayoutGrid size={28} />} title="No destinations match" action={filtered ? <button className="btn btn-soft" onClick={reset}>Clear filters</button> : undefined}>
          {scope === 'seen' ? 'No routes from this airport have been searched yet.' : 'Try another search, region or theme.'}
        </EmptyState></div>
      ) : (
        <div className={`dest-grid ${busy && page === 1 ? 'is-refreshing' : ''}`}>
          {items.map((d) => (
            <DestinationCard key={d.key} d={d} fav={favourites.includes(d.airport)} onFav={() => void toggleFavourite(d.airport)} onExplore={() => onExplore(d.airport)}
              onSearch={origin && !loading ? () => onSearchRoute(origin.code, d.airport) : undefined} />
          ))}
        </div>
      )}
      {view === 'grid' && meta && items.length < meta.total && (
        <div className="load-more"><button className="btn btn-soft" onClick={loadMore} disabled={busy}>{busy ? <span className="spinner dark" /> : null}Show more destinations ({(meta.total - items.length).toLocaleString()} more)</button></div>
      )}
      <p className="muted small credits"><MapIcon size={12} /> Photos from Wikipedia / Wikimedia Commons under their stated free licences (credited on each image). Illustrations are shown where no free photo exists.</p>
    </div>
  );
}
