import { useCallback, useEffect, useRef, useState } from 'react';
import { Plane, RefreshCw, ServerCrash } from 'lucide-react';
import { AuthModal, Header } from './components/Header';
import { api, errorText } from './lib/api';
import { addDaysIso, rememberAirports, toRef, todayIso } from './lib/format';
import { useDepartureAirport } from './lib/departure';
import { useFeatureState, type DemoService } from './lib/features';
import { navigate, readSession, useRoute, writeSession, type Route } from './lib/router';
import { Loading } from './components/ui';
import type { Airport, AirportRef, Flight, SearchForm, SearchResponse, SearchState, TripType } from './lib/types';
import { emptyForm, isCurrentForm, searchBody } from './lib/validation';
import { AccountPage } from './pages/AccountPage';
import { CarsPage } from './pages/CarsPage';
import { DealsPage } from './pages/DealsPage';
import { DestinationsPage } from './pages/DestinationsPage';
import { DetailsPage } from './pages/DetailsPage';
import { GuidesPage } from './pages/GuidesPage';
import HomePage from './pages/HomePage';
import { InsightsPage } from './pages/InsightsPage';
import { PackagesPage } from './pages/PackagesPage';
import { PlannerPage } from './pages/PlannerPage';
import { ResultsPage } from './pages/ResultsPage';
import { StaysPage } from './pages/StaysPage';
import { ToursPage } from './pages/ToursPage';
import { AuthProvider, PrefsProvider, ToastProvider, useAuth } from './state';

const LOCAL_RECENT_KEY = 'fc-recent-searches-v2';
export type LocalRecent = { form: SearchForm; at: string };
export type SearchRouteFn = (from: string, to: string, dates?: { departure?: string; returnDate?: string | null; tripType?: TripType }) => void;
export type ExploreFn = (code: string) => void;
const REQUIRED_API = '0.3.0';

export default function App() {
  return (
    <ToastProvider>
      <PrefsProvider>
        <AuthProvider>
          <Shell />
          <AuthModal />
        </AuthProvider>
      </PrefsProvider>
    </ToastProvider>
  );
}

async function lookupAirports(codes: string[]): Promise<AirportRef[]> {
  const list = await api<Airport[]>(`/api/airports/lookup?codes=${codes.join(',')}`);
  rememberAirports(list);
  return codes.map((c) => list.find((a) => a.code === c)).filter(Boolean).map((a) => toRef(a!));
}

function Shell() {
  const route = useRoute();
  const features = useFeatureState();
  const { user, recordView } = useAuth();
  const departure = useDepartureAirport(user?.preferences.home_airport);
  const [form, setForm] = useState<SearchForm>(() => emptyForm(departure.origin));
  const [search, setSearch] = useState<SearchState | null>(() => { const s = readSession<SearchState>('fc-search'); return s && isCurrentForm(s.query) ? s : null; });
  const [selected, setSelected] = useState<Flight | null>(() => readSession<Flight>('fc-selected'));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [apiProblem, setApiProblem] = useState<'outdated' | 'unreachable' | null>(null);
  const inFlight = useRef<AbortController | null>(null);
  const update = useCallback((p: Partial<SearchForm>) => setForm((f) => ({ ...f, ...p })), []);

  // Detect a missing or outdated API server instead of failing later with "Not Found".
  useEffect(() => {
    api<{ api_version: string }>('/api/meta')
      .then((m) => setApiProblem(m.api_version < REQUIRED_API ? 'outdated' : null))
      .catch((err) => setApiProblem((err as { status?: number }).status === 404 ? 'outdated' : 'unreachable'));
  }, []);

  // Keep the form's departure airport in sync with the remembered/detected one.
  useEffect(() => {
    setForm((f) => (f.origin?.code === departure.origin?.code ? f : {
      ...f, origin: departure.origin,
      legs: f.legs.map((l, i) => (i === 0 && (!l.origin || l.origin.code === f.origin?.code) ? { ...l, origin: departure.origin } : l)),
    }));
  }, [departure.origin]);

  // Apply account travel preferences once after sign-in.
  const appliedPrefsFor = useRef<number | null>(null);
  useEffect(() => {
    if (!user || appliedPrefsFor.current === user.id) return;
    appliedPrefsFor.current = user.id;
    const p = user.preferences;
    setForm((f) => ({ ...f, cabin: p.cabin ?? f.cabin, passengers: p.passengers ? { ...f.passengers, adults: p.passengers } : f.passengers }));
  }, [user]);

  const runSearch = useCallback(async (f: SearchForm) => {
    inFlight.current?.abort();
    const ctrl = new AbortController();
    inFlight.current = ctrl;
    setError(null);
    setLoading(true);
    setForm(f);
    try {
      const response = await api<SearchResponse>('/api/flights/search', { method: 'POST', signal: ctrl.signal, body: searchBody(f) });
      const state: SearchState = { query: f, response, searchedAt: new Date().toISOString() };
      setSearch(state);
      writeSession('fc-search', state);
      rememberLocally(f);
      setHistoryVersion((v) => v + 1);
      navigate({ page: 'results' });
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setError(errorText(err));
      navigate({ page: 'home' });
      window.setTimeout(() => document.getElementById('search-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 200);
    } finally {
      if (inFlight.current === ctrl) setLoading(false);
    }
  }, []);

  /** Run a real search for a route (codes are verified first). Uses the form's dates, or two weeks from today. */
  const searchRoute = useCallback<SearchRouteFn>(async (from, to, dates) => {
    let airports: AirportRef[];
    try { airports = await lookupAirports([from, to]); } catch (err) { setError(errorText(err)); return; }
    if (airports.length < 2) { setError('That route uses an airport we could not verify.'); return; }
    const tripType = dates?.tripType === 'multi-city' ? 'round-trip' : dates?.tripType ?? (form.tripType === 'multi-city' ? 'round-trip' : form.tripType);
    const departureDate = dates?.departure && dates.departure >= todayIso() ? dates.departure : form.departure && form.departure >= todayIso() ? form.departure : addDaysIso(14);
    let returnDate = '';
    if (tripType === 'round-trip') {
      const wanted = dates?.returnDate ?? form.returnDate;
      returnDate = wanted && wanted >= departureDate ? wanted : addDaysIso(7, new Date(`${departureDate}T12:00:00`));
    }
    void runSearch({ ...form, tripType, origin: airports[0], destination: airports[1], departure: departureDate, returnDate });
  }, [form, runSearch]);

  /** Put a destination into the search form and bring the form into view. */
  const explore = useCallback<ExploreFn>(async (code) => {
    try {
      const [dest] = await lookupAirports([code]);
      if (dest) setForm((f) => ({ ...f, tripType: f.tripType === 'multi-city' ? 'round-trip' : f.tripType, destination: dest }));
    } catch (err) { setError(errorText(err)); }
    navigate({ page: 'home' });
    window.setTimeout(() => document.getElementById('search-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 200);
  }, []);

  const select = (f: Flight, query: SearchForm | null = search?.query ?? null) => {
    setSelected(f);
    writeSession('fc-selected', f);
    recordView(f, query);
    navigate({ page: 'details' });
  };

  const origin = departure.origin;
  // Services with only simulated inventory are reachable only when the API enables them.
  const gated: Partial<Record<Route['page'], DemoService>> = { stays: 'stays', packages: 'packages', cars: 'cars', tours: 'tours' };
  const needs = gated[route.page];
  let page;
  if (needs && !features) page = <div className="container page"><Loading /></div>;
  else if (needs && !features?.has(needs)) page = <NotAvailable />;
  else switch (route.page) {
    case 'results':
      page = search ? <ResultsPage key={search.searchedAt} search={search} onEdit={() => { setForm(search.query); navigate({ page: 'home' }); }} onSelect={(f) => select(f)} /> : <NoSearch />;
      break;
    case 'details':
      page = selected ? <DetailsPage flight={selected} query={search?.query ?? null} hasResults={!!search} /> : <NoSearch text="Choose a flight from your search results to see its full itinerary." />;
      break;
    case 'insights': page = <InsightsPage historyVersion={historyVersion} onSearchRoute={searchRoute} />; break;
    case 'destinations': page = <DestinationsPage origin={origin} onOriginChange={departure.setOrigin} onExplore={explore} onSearchRoute={searchRoute} loading={loading} />; break;
    case 'deals': page = <DealsPage origin={origin} onOriginChange={departure.setOrigin} onSearchRoute={searchRoute} loading={loading} historyVersion={historyVersion} />; break;
    case 'account': page = <AccountPage tab={route.tab} onOpenFlight={(f, q) => { if (q && isCurrentForm(q)) setForm(q); select(f, q && isCurrentForm(q) ? q : null); }} onSearchRoute={searchRoute} onExplore={explore} />; break;
    case 'stays': page = <StaysPage key={route.location ?? ''} location={route.location} />; break;
    case 'packages':
      page = <PackagesPage location={route.location} origin={origin} onOriginChange={departure.setOrigin} onOpenFlight={(f, q) => { setForm(q); setHistoryVersion((v) => v + 1); select(f, q); }} />;
      break;
    case 'cars': page = <CarsPage key={`${route.tab}-${route.location ?? ''}`} tab={route.tab} location={route.location} />; break;
    case 'tours': page = <ToursPage key={route.location ?? ''} kind={route.kind} location={route.location} />; break;
    case 'planner': page = <PlannerPage key={route.location ?? ''} location={route.location} origin={origin} onSearchRoute={searchRoute} />; break;
    case 'guides': page = <GuidesPage location={route.location} origin={origin} onSearchRoute={searchRoute} />; break;
    default:
      page = (
        <HomePage form={form} update={update} onOriginChange={(a: AirportRef | null) => { departure.setOrigin(a); update({ origin: a }); }} onSearch={runSearch} loading={loading} error={error}
          historyVersion={historyVersion} onExplore={explore} onSearchRoute={searchRoute}
          location={{ status: departure.status, geoState: departure.geoState, locate: () => departure.locate(true), dismiss: departure.dismissPrompt }} />
      );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <Header route={route} />
      {apiProblem && (
        <div className="api-banner" role="alert">
          <ServerCrash size={16} />
          {apiProblem === 'outdated'
            ? <span>The FlyCompare API server is running an older version, so sign-in, insights and airport search are unavailable. Restart the backend (see README → Running locally).</span>
            : <span>Can’t reach the FlyCompare API server. Check that the backend is running on port 8000.</span>}
          <button className="link-btn small" onClick={() => window.location.reload()}><RefreshCw size={13} /> Retry</button>
        </div>
      )}
      <main id="main">{page}</main>
      {loading && route.page !== 'home' && <div className="global-loading" role="status"><span className="spinner" /> Searching flights…</div>}
      <footer className="footer">
        <div className="footer-inner">
          <a className="brand" href="#/"><span className="brand-mark"><Plane size={16} /></span><span>FlyCompare <b>AI</b></span></a>
          <p>Compare complete journeys. FlyCompare compares offers; it does not sell or issue tickets.</p>
          <span>Airport data: OurAirports · Map: Natural Earth · © {new Date().getFullYear()} FlyCompare AI</span>
        </div>
      </footer>
    </div>
  );
}

function NotAvailable() {
  return (
    <div className="container page">
      <div className="card empty-state"><Plane size={32} /><h3>Not available yet</h3>
        <p>This service is coming soon. We only show offers from real providers, and none is connected for it yet.</p>
        <button className="btn btn-primary" onClick={() => navigate({ page: 'home' })}>Search flights</button></div>
    </div>
  );
}

function NoSearch({ text = 'Search for flights to compare available offers.' }: { text?: string }) {
  return (
    <div className="container page">
      <div className="card empty-state"><Plane size={32} /><h3>Nothing to show yet</h3><p>{text}</p><button className="btn btn-primary" onClick={() => navigate({ page: 'home' })}>Start a search</button></div>
    </div>
  );
}

function rememberLocally(f: SearchForm) {
  // Visitors who are not signed in keep a short recent-search list in this browser only.
  try {
    const key = (x: SearchForm) => `${x.tripType}|${x.origin?.code}|${x.destination?.code}|${x.departure}|${x.returnDate}|${x.legs.map((l) => l.origin?.code + '-' + l.destination?.code + l.date).join()}`;
    const next = [{ form: f, at: new Date().toISOString() }, ...readLocalRecent().filter((x) => key(x.form) !== key(f))].slice(0, 8);
    localStorage.setItem(LOCAL_RECENT_KEY, JSON.stringify(next));
  } catch { /* storage unavailable */ }
}

export function readLocalRecent(): LocalRecent[] {
  try { return (JSON.parse(localStorage.getItem(LOCAL_RECENT_KEY) ?? '[]') as LocalRecent[]).filter((r) => isCurrentForm(r.form)); } catch { return []; }
}
