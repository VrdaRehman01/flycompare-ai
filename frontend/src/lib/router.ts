import { useEffect, useState } from 'react';

// Hash-based routing keeps deep links and the browser back button working
// without server configuration.
// Travel pages take an optional location (airport/metro code or City|CC key) so
// pages can hand a destination to each other, e.g. a guide linking to its stays.
export type TourKind = 'group' | 'private';
export type GroundTab = 'rental' | 'transfers';
export type Route =
  | { page: 'home' } | { page: 'results' } | { page: 'details' } | { page: 'insights' }
  | { page: 'destinations' } | { page: 'deals' } | { page: 'account'; tab: AccountTab }
  | { page: 'stays'; location?: string } | { page: 'packages'; location?: string }
  | { page: 'cars'; tab: GroundTab; location?: string } | { page: 'tours'; kind: TourKind; location?: string }
  | { page: 'planner'; location?: string } | { page: 'guides'; location?: string };
export type AccountTab = 'profile' | 'saved' | 'favourites' | 'recent' | 'history' | 'alerts' | 'preferences' | 'security';
const ACCOUNT_TABS: AccountTab[] = ['profile', 'saved', 'favourites', 'recent', 'history', 'alerts', 'preferences', 'security'];

export function parseHash(hash: string): Route {
  const [page, sub, extra] = hash.replace(/^#\/?/, '').split('/');
  const loc = (v?: string) => { try { return v ? decodeURIComponent(v) : undefined; } catch { return undefined; } };
  switch (page) {
    case 'results': return { page: 'results' };
    case 'flight': return { page: 'details' };
    case 'insights': return { page: 'insights' };
    case 'destinations': return { page: 'destinations' };
    case 'deals': return { page: 'deals' };
    case 'account': return { page: 'account', tab: ACCOUNT_TABS.includes(sub as AccountTab) ? (sub as AccountTab) : 'profile' };
    case 'stays': return { page: 'stays', location: loc(sub) };
    case 'packages': return { page: 'packages', location: loc(sub) };
    case 'planner': return { page: 'planner', location: loc(sub) };
    case 'guides': return { page: 'guides', location: loc(sub) };
    case 'cars': return { page: 'cars', tab: sub === 'transfers' ? 'transfers' : 'rental', location: loc(extra) };
    case 'tours': return { page: 'tours', kind: sub === 'private' ? 'private' : 'group', location: loc(extra) };
    default: return { page: 'home' };
  }
}

export function hrefFor(route: Route): string {
  const loc = 'location' in route && route.location ? `/${encodeURIComponent(route.location)}` : '';
  switch (route.page) {
    case 'home': return '#/';
    case 'details': return '#/flight';
    case 'account': return `#/account/${route.tab}`;
    case 'cars': return `#/cars/${route.tab}${loc}`;
    case 'tours': return `#/tours/${route.kind}${loc}`;
    default: return `#/${route.page}${loc}`;
  }
}

export function navigate(route: Route) {
  const href = hrefFor(route);
  if (window.location.hash !== href) window.location.hash = href;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onHash = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return route;
}

/* Session storage keeps the last search and the selected offer across reloads. */
export function readSession<T>(key: string): T | null {
  try { const v = window.sessionStorage.getItem(key); return v ? JSON.parse(v) as T : null; } catch { return null; }
}
export function writeSession(key: string, value: unknown) {
  try { if (value == null) window.sessionStorage.removeItem(key); else window.sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked */ }
}
