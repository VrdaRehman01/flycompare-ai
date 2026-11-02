import { useEffect, useState, type ReactNode } from 'react';
import { ArrowRight, BookOpen, CarFront, ChevronRight, Clock3, History, Hotel, Package, Search, ShieldCheck, Sparkles, TrendingDown, UserRound, Users, Wand2 } from 'lucide-react';
import { readLocalRecent, type ExploreFn, type SearchRouteFn } from '../App';
import { Discovery } from '../components/Discovery';
import { WeatherDiscovery } from '../components/WeatherDiscovery';
import { SearchCard } from '../components/SearchCard';
import type { LocationStatus } from '../components/AirportField';
import { HeroCredit, HeroPhoto } from '../components/HeroPhoto';
import { api } from '../lib/api';
import { dayMonth, todayIso } from '../lib/format';
import type { GeoState } from '../lib/geo';
import { useFeatures, type DemoService } from '../lib/features';
import { navigate, type Route } from '../lib/router';
import type { AirportRef, HistoryItem, SearchForm } from '../lib/types';
import { passengerSummary } from '../lib/validation';
import { useAuth } from '../state';

type Recent = { key: string; title: string; dates: string; future: boolean; run: () => void };

const SERVICES: { label: string; hint: string; icon: ReactNode; withCity: boolean; needs?: DemoService; route: (dest?: string) => Route }[] = [
  { label: 'Hotels & Homes', hint: 'Hotels, apartments and resorts', icon: <Hotel size={20} />, withCity: true, needs: 'stays', route: (d) => ({ page: 'stays', location: d }) },
  { label: 'Flight & Hotel', hint: 'One price for the whole trip', icon: <Package size={20} />, withCity: false, needs: 'packages', route: (d) => ({ page: 'packages', location: d }) },
  { label: 'Cars & transfers', hint: 'Rentals and airport rides', icon: <CarFront size={20} />, withCity: true, needs: 'cars', route: (d) => ({ page: 'cars', tab: 'rental', location: d }) },
  { label: 'Group tours', hint: 'Guided, priced per person', icon: <Users size={20} />, withCity: true, needs: 'tours', route: (d) => ({ page: 'tours', kind: 'group', location: d }) },
  { label: 'Private tours', hint: 'Your own guide and car', icon: <UserRound size={20} />, withCity: true, needs: 'tours', route: (d) => ({ page: 'tours', kind: 'private', location: d }) },
  { label: 'Trip planner', hint: 'Day-by-day plan and budget', icon: <Wand2 size={20} />, withCity: false, route: (d) => ({ page: 'planner', location: d }) },
  { label: 'Travel guides', hint: 'Best months, sights, areas', icon: <BookOpen size={20} />, withCity: false, route: (d) => ({ page: 'guides', location: d }) },
  { label: 'Deals', hint: 'Low fares seen in searches', icon: <TrendingDown size={20} />, withCity: false, route: () => ({ page: 'deals' }) },
  { label: 'Destinations', hint: 'Ideas by theme and region', icon: <Search size={20} />, withCity: false, route: () => ({ page: 'destinations' }) },
];

type Props = {
  form: SearchForm; update: (p: Partial<SearchForm>) => void; onOriginChange: (a: AirportRef | null) => void; onSearch: (f: SearchForm) => void;
  loading: boolean; error: string | null; historyVersion: number; onExplore: ExploreFn; onSearchRoute: SearchRouteFn;
  location: { status: LocationStatus; geoState: GeoState; locate: () => void; dismiss: () => void };
};

export default function HomePage({ form, update, onOriginChange, onSearch, loading, error, historyVersion, onExplore, onSearchRoute, location }: Props) {
  const { user, ready } = useAuth();
  const features = useFeatures();
  const [recent, setRecent] = useState<Recent[] | null>(null);
  const today = todayIso();

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setRecent(readLocalRecent().slice(0, 4).map(({ form: f, at }) => {
        const first = f.tripType === 'multi-city' ? f.legs[0] : null;
        const start = first ? first.date : f.departure;
        const future = start >= today;
        const title = f.tripType === 'multi-city' ? f.legs.map((l) => l.origin?.code).concat(f.legs[f.legs.length - 1].destination?.code).join(' → ') : `${f.origin?.code} → ${f.destination?.code}`;
        return {
          key: at, title, future,
          dates: `${dayMonth(start)}${f.tripType === 'round-trip' ? ` – ${dayMonth(f.returnDate)}` : f.tripType === 'one-way' ? ' · One way' : ' · Multi-city'} · ${passengerSummary(f.passengers)}`,
          run: () => (future ? onSearch(f) : (update({ ...f, departure: '', returnDate: '' }), document.getElementById('search-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))),
        };
      }));
      return;
    }
    api<HistoryItem[]>('/api/flights/history')
      .then((rows) => {
        const seen = new Set<string>();
        setRecent(rows.filter((h) => h.origin_code && h.destination_code && h.trip_type !== 'multi-city').filter((h) => {
          const k = `${h.origin_code}-${h.destination_code}-${h.departure_date}-${h.return_date}`;
          return seen.has(k) ? false : (seen.add(k), true);
        }).slice(0, 4).map((h) => {
          const future = h.departure_date >= today;
          return {
            key: String(h.id), title: `${h.origin_code} → ${h.destination_code}`, future,
            dates: `${dayMonth(h.departure_date)}${h.return_date ? ` – ${dayMonth(h.return_date)}` : ' · One way'}${future ? '' : ' · past dates'}`,
            run: () => onSearchRoute(h.origin_code!, h.destination_code!, future ? { departure: h.departure_date, returnDate: h.return_date, tripType: h.trip_type } : { tripType: h.trip_type }),
          };
        }));
      })
      .catch(() => setRecent([]));
  }, [user, ready, historyVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <section className="hero">
        <HeroPhoto />
        <div className="hero-inner">
          <span className="eyebrow-pill"><Sparkles size={13} /> FLIGHT COMPARISON, IN FULL</span>
          <h1>See the whole journey<br /><span>before you choose it.</span></h1>
          <p>Compare complete itineraries from airports worldwide: bags, fare rules, seats and observed price history, side by side. No account needed.</p>
        </div>
        <HeroCredit />
      </section>

      <section className="container search-section">
        <SearchCard form={form} update={update} onOriginChange={onOriginChange} onSearch={onSearch} loading={loading} error={error} location={location} />
      </section>

      <section className="container section">
        <div className="section-head"><h2>Plan the whole trip</h2><span className="muted small">Everything after the flight, in one place</span></div>
        <div className="services-grid">
          {SERVICES.filter((s) => !s.needs || features.has(s.needs)).map((s) => {
            const dest = form.destination?.code;
            return (
              <button key={s.label} className="card service-tile" onClick={() => navigate(s.route(dest))}>
                <span className="service-icon">{s.icon}</span>
                <b>{s.label}</b><small>{s.hint}{dest && s.withCity ? ` in ${form.destination!.city}` : ''}</small>
              </button>
            );
          })}
        </div>
      </section>

      <section className="container section">
        <div className="section-head">
          <h2>Recent searches</h2>
          {user ? <button className="link-btn" onClick={() => navigate({ page: 'account', tab: 'history' })}>View all</button> : recent?.length ? <span className="muted small">Saved in this browser only</span> : null}
        </div>
        {recent === null ? <div className="recent-grid">{[0, 1, 2, 3].map((i) => <div key={i} className="card recent-card skeleton" />)}</div> : recent.length ? (
          <div className="recent-grid">
            {recent.map((r) => (
              <button key={r.key} className="card recent-card" onClick={r.run} disabled={loading} title={r.future ? 'Search this trip again' : 'Dates have passed — choose new dates'}>
                <span className="icon-circle"><Clock3 size={17} /></span>
                <span className="recent-text"><b>{r.title}</b><small>{r.dates}</small></span>
                <ChevronRight size={16} className="chev" />
              </button>
            ))}
          </div>
        ) : <div className="empty-inline"><History size={18} /> Your recent searches will appear here after your first flight search.</div>}
      </section>

      <WeatherDiscovery origin={form.origin} onExplore={onExplore} onSearchRoute={onSearchRoute} />
      <Discovery origin={form.origin} onExplore={onExplore} onSearchRoute={onSearchRoute} />

      <section className="container section features">
        {[
          { icon: <TrendingDown size={22} />, t: 'Transparent ranking', s: 'Price, time and stops — weights shown' },
          { icon: <Search size={22} />, t: 'Real provider search', s: 'Offers come from Duffel' },
          { icon: <Sparkles size={22} />, t: 'Data-backed insights', s: 'Built from real searches only' },
          { icon: <ShieldCheck size={22} />, t: 'Honest labelling', s: 'Test, demo and live data marked' },
        ].map((f) => <div key={f.t} className="feature"><span className="feature-icon">{f.icon}</span><b>{f.t}</b><small>{f.s}</small></div>)}
      </section>
      <div className="container home-cta"><button className="link-btn" onClick={() => navigate({ page: 'insights' })}>See what travellers are searching <ArrowRight size={14} /></button></div>
    </>
  );
}
  