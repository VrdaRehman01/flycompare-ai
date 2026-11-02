import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, Clock3, Globe2, Lock, Star, User as UserIcon } from 'lucide-react';
import { readLocalRecent, type SearchRouteFn } from '../App';
import { api, errorText } from '../lib/api';
import { dayMonth, money, relativeTime, todayIso } from '../lib/format';
import type { PopularRoute, PopularRoutes as PopularRoutesData, RouteSnapshot, SavedRoute, TripType } from '../lib/types';
import { useAuth, useToast } from '../state';
import { Loading, Notice, StatusPill } from './ui';

type Tab = 'mine' | 'saved' | 'all';
type Row = {
  key: string; origin: { code: string; city: string; country: string | null }; destination: { code: string; city: string; country: string | null };
  searches?: number; share?: number; when?: string; whenExact?: boolean; lastFare?: RouteSnapshot | null; saved?: boolean;
  trip?: { trip_type: TripType; departure_date: string; return_date: string | null } | null; note?: string; mix?: Record<string, number>;
};

/** "today", "yesterday", "3 days ago" for a day-only date (public routes never show a time). */
export function dayAgo(isoDay: string, now = new Date()) {
  const [y, m, d] = isoDay.split('-').map(Number);
  const days = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - new Date(y, m - 1, d).getTime()) / 86400000);
  return days <= 0 ? 'today' : days === 1 ? 'yesterday' : days < 7 ? `${days} days ago` : dayMonth(isoDay);
}

export function PopularRoutes({ onSearchRoute, loading, version }: { onSearchRoute: SearchRouteFn; loading: boolean; version: number }) {
  const { user, ready, openAuth } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('all');
  const [state, setState] = useState<{ loading: boolean; rows: Row[]; basis?: string; total?: number; error?: string }>({ loading: true, rows: [] });
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());

  useEffect(() => { if (ready) setTab(user ? 'mine' : 'all'); }, [ready, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSaved = useCallback(async () => {
    if (!user) { setSavedKeys(new Set()); return [] as SavedRoute[]; }
    const list = await api<SavedRoute[]>('/api/account/saved-routes');
    setSavedKeys(new Set(list.map((r) => `${r.origin.code}-${r.destination.code}`)));
    return list;
  }, [user]);

  useEffect(() => {
    if (!ready) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    const run = async (): Promise<{ rows: Row[]; basis?: string; total?: number }> => {
      const saved = user ? await loadSaved() : [];
      if (tab === 'saved') {
        return {
          rows: saved.map((r) => ({ key: `${r.origin.code}-${r.destination.code}`, origin: r.origin, destination: r.destination, lastFare: r.last_fare, saved: true, when: r.saved_at, whenExact: true, note: 'Saved' })),
          basis: 'Routes you saved. Saving does not track prices; search to see current fares.',
        };
      }
      if (tab === 'mine' && !user) {
        // Signed-out visitors: only what this browser remembers, never server data.
        const seen = new Map<string, Row>();
        for (const { form: f, at } of readLocalRecent()) {
          if (f.tripType === 'multi-city' || !f.origin || !f.destination) continue;
          const key = `${f.origin.code}-${f.destination.code}`;
          const row = seen.get(key);
          if (row) { row.searches = (row.searches ?? 0) + 1; continue; }
          seen.set(key, { key, origin: f.origin, destination: f.destination, searches: 1, when: at, whenExact: true, trip: { trip_type: f.tripType, departure_date: f.departure, return_date: f.returnDate || null } });
        }
        return { rows: [...seen.values()], basis: 'Searched in this browser only. Sign in to keep your routes across devices.' };
      }
      const data = await api<PopularRoutesData>(`/api/routes/popular?scope=${tab === 'mine' ? 'me' : 'all'}&limit=12`);
      return {
        rows: data.routes.map((r: PopularRoute) => ({
          key: `${r.origin.code}-${r.destination.code}`, origin: r.origin, destination: r.destination, searches: r.searches, share: r.share,
          when: r.last_searched_at ?? r.last_searched_day, whenExact: !!r.last_searched_at, lastFare: r.last_fare, saved: r.saved, trip: r.last_trip ?? null, mix: r.data_status_mix,
        })),
        basis: data.basis, total: data.total_searches,
      };
    };
    run().then((r) => { if (live) setState({ loading: false, ...r }); }).catch((err) => { if (live) setState({ loading: false, rows: [], error: errorText(err) }); });
    return () => { live = false; };
  }, [tab, user?.id, ready, version]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleSave = async (row: Row) => {
    if (!user) { openAuth('login', 'Sign in to save routes'); return; }
    const isSaved = savedKeys.has(row.key);
    try {
      const list = isSaved
        ? await api<SavedRoute[]>(`/api/account/saved-routes/${row.origin.code}/${row.destination.code}`, { method: 'DELETE' })
        : await api<SavedRoute[]>('/api/account/saved-routes', { method: 'POST', body: { origin: row.origin.code, destination: row.destination.code } });
      setSavedKeys(new Set(list.map((r) => `${r.origin.code}-${r.destination.code}`)));
      if (tab === 'saved') setState((s) => ({ ...s, rows: s.rows.filter((r) => list.some((x) => `${x.origin.code}-${x.destination.code}` === r.key)) }));
      toast('success', isSaved ? 'Route removed' : 'Route saved');
    } catch (err) { toast('error', errorText(err)); }
  };

  const go = (row: Row) => {
    const future = row.trip && row.trip.departure_date >= todayIso();
    onSearchRoute(row.origin.code, row.destination.code, future
      ? { departure: row.trip!.departure_date, returnDate: row.trip!.return_date, tripType: row.trip!.trip_type }
      : row.trip ? { tripType: row.trip.trip_type } : undefined);
  };

  const tabs: [Tab, string, typeof Globe2][] = [['mine', 'Your routes', UserIcon], ['saved', 'Saved', Star], ['all', 'Across FlyCompare', Globe2]];
  return (
    <section className="routes-section" aria-labelledby="routes-h">
      <div className="section-head routes-head">
        <div><h2 id="routes-h">Popular routes</h2><p className="muted small">{state.basis}</p></div>
        <div className="seg" role="tablist" aria-label="Which routes">
          {tabs.map(([k, label, Icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'active' : ''}
              onClick={() => (k === 'saved' && !user ? openAuth('login', 'Sign in to see saved routes', () => setTab('saved')) : setTab(k))}>
              <Icon size={14} /> {label}{k === 'saved' && !user && <Lock size={11} />}
            </button>
          ))}
        </div>
      </div>
      {state.error && <Notice kind="error">{state.error}</Notice>}
      {state.loading && !state.rows.length && <Loading label="Loading routes…" />}
      {!state.loading && !state.error && !state.rows.length && (
        <div className="empty-inline">
          <Clock3 size={16} />
          {tab === 'all' ? 'No route has been searched often enough to show here yet.' : tab === 'saved' ? 'No saved routes yet. Use the star on any route to save it.' : 'Your searched routes will appear here after your first search.'}
          {tab === 'mine' && !user && <button className="link-btn small" onClick={() => openAuth('login', 'Sign in to keep your routes')}>Sign in</button>}
        </div>
      )}
      {state.rows.length > 0 && (
        <ul className="route-cards">
          {state.rows.map((r) => {
            const saved = savedKeys.has(r.key);
            const label = `Search flights from ${r.origin.city} (${r.origin.code}) to ${r.destination.city} (${r.destination.code})`;
            return (
              <li key={r.key} className="route-card">
                <button className="route-hit" onClick={() => go(r)} disabled={loading} aria-label={label} />
                <div className="route-codes" aria-hidden="true">
                  <span><b>{r.origin.code}</b><small>{r.origin.city}</small></span>
                  <i className="route-line" />
                  <span><b>{r.destination.code}</b><small>{r.destination.city}</small></span>
                </div>
                <div className="route-meta">
                  <span className="route-dest">{r.destination.city}{r.destination.country ? `, ${r.destination.country}` : ''}</span>
                  <span className="route-stats">
                    {r.searches != null && <>{r.searches} search{r.searches === 1 ? '' : 'es'}{r.share != null && tab === 'all' ? ` · ${r.share}% of shown` : ''}</>}
                    {r.when && <> · {r.note ? `${r.note} ` : 'last '}{r.whenExact ? relativeTime(r.when) : dayAgo(r.when)}</>}
                  </span>
                  {r.lastFare?.lowest_price != null && r.lastFare.currency
                    ? <span className="route-fare">Last seen <b>{money(r.lastFare.lowest_price, r.lastFare.currency)}</b> <StatusPill status={r.lastFare.data_status} /><small>{relativeTime(r.lastFare.observed_at!)}</small></span>
                    : <span className="route-fare muted">No fare seen yet</span>}
                </div>
                <button className={`route-star ${saved ? 'on' : ''}`} onClick={() => void toggleSave(r)} aria-pressed={saved} aria-label={saved ? `Remove ${r.origin.code}–${r.destination.code} from saved routes` : `Save ${r.origin.code}–${r.destination.code}`}>
                  <Star size={16} />
                </button>
                <span className="route-go" aria-hidden="true"><ArrowRight size={22} /></span>
              </li>
            );
          })}
        </ul>
      )}
      {tab === 'all' && state.total != null && state.rows.length > 0 && (
        <p className="muted small routes-note">Shares are of the {state.total} searches on the routes shown. Search counts include demo and test searches made while FlyCompare is in development.</p>
      )}
    </section>
  );
}
