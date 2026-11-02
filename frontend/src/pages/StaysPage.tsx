import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { BedDouble, Building2, Car, Coffee, Compass, Home, Hotel, MapPin, Palmtree, Search, ShieldCheck, Tent, Wifi } from 'lucide-react';
import { AirportField } from '../components/AirportField';
import { Listbox } from '../components/Listbox';
import { DateField } from '../components/Pickers';
import { GuestPicker, ProviderNotice, Stars, TravelHero, useTrip } from '../components/TravelUI';
import { EmptyState, Loading, Notice, Price } from '../components/ui';
import { api, errorText } from '../lib/api';
import { navigate } from '../lib/router';
import { MediaPhoto } from '../components/MediaPhoto';
import { CheckRow } from './ResultsPage';
import { PROPERTY_LABEL, nightsBetween, reviewLabel, type PropertyType, type Stay, type StaysResponse } from '../lib/travel';

type Tab = 'all' | 'hotels' | 'homes' | 'resorts' | 'hostels';
type Sort = 'recommended' | 'price' | 'rating' | 'distance';
const TABS: { value: Tab; label: string; icon: ReactNode; types: PropertyType[] }[] = [
  { value: 'all', label: 'All stays', icon: <BedDouble size={15} />, types: ['hotel', 'apartment', 'resort', 'hostel', 'villa'] },
  { value: 'hotels', label: 'Hotels', icon: <Hotel size={15} />, types: ['hotel'] },
  { value: 'homes', label: 'Homes & apartments', icon: <Home size={15} />, types: ['apartment', 'villa'] },
  { value: 'resorts', label: 'Resorts', icon: <Palmtree size={15} />, types: ['resort'] },
  { value: 'hostels', label: 'Hostels', icon: <Tent size={15} />, types: ['hostel'] },
];
const AMENITY_FILTERS = ['Free cancellation', 'Breakfast included', 'Pool', 'Kitchen', 'Parking', 'Airport shuttle'];

/** Value score: rating per unit of price, nudged by distance. Used for "Recommended". */
export function stayScore(s: Stay, cheapest: number) {
  const rating = (s.review_score ?? 7) / 10;
  // Square root softens price so a much cheaper but basic place doesn't always win.
  const price = Math.sqrt(cheapest / Math.max(s.nightly_price, 1));
  const near = 1 / (1 + (s.distance_km ?? 5) / 6);
  const privateRoom = s.property_type === 'hostel' ? 0 : 0.1; // shared dorms rarely suit couples or families
  return rating * 0.55 + price * 0.2 + near * 0.15 + privateRoom;
}

const hasAmenity = (s: Stay, a: string) =>
  a === 'Free cancellation' ? !!s.free_cancellation : a === 'Breakfast included' ? !!s.breakfast_included : s.amenities.some((x) => x.toLowerCase().includes(a.toLowerCase()));

export function useStaysSearch() {
  const [data, setData] = useState<StaysResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (p: { location: string; check_in: string; check_out: string; adults: number; children: number; rooms: number }, signal?: AbortSignal) => {
    setBusy(true);
    setError(null);
    try {
      const q = new URLSearchParams({ ...p, adults: String(p.adults), children: String(p.children), rooms: String(p.rooms) });
      const res = await api<StaysResponse>(`/api/stays/search?${q}`, { signal });
      setData(res);
      return res;
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError(errorText(err));
      return null;
    } finally { setBusy(false); }
  }, []);
  return { data, error, busy, run };
}

export function StaysPage({ location }: { location?: string }) {
  const [trip, setTrip] = useTrip(location);
  const { data, error, busy, run } = useStaysSearch();
  const [tab, setTab] = useState<Tab>('all');
  const [sort, setSort] = useState<Sort>('recommended');
  const [stars, setStars] = useState<number[]>([]);
  const [minScore, setMinScore] = useState(0);
  const [amenities, setAmenities] = useState<string[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [maxNightly, setMaxNightly] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = (e?: FormEvent) => {
    e?.preventDefault();
    if (!trip.destination) { setFormError('Choose where you want to stay.'); return; }
    if (!trip.start || !trip.end || trip.end <= trip.start) { setFormError('Choose check-in and check-out dates.'); return; }
    setFormError(null);
    setMaxNightly(null); setAreas([]);
    void run({ location: trip.destination.code, check_in: trip.start, check_out: trip.end, adults: trip.adults, children: trip.children, rooms: trip.rooms });
  };
  // Search straight away when arriving with a destination (from a guide, planner or link).
  useEffect(() => { if (trip.destination && !data && !busy) search(); }, [trip.destination?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const results = data?.results ?? [];
  const priceCap = results.length ? Math.ceil(Math.max(...results.map((r) => r.nightly_price))) : 0;
  const counts = useMemo(() => Object.fromEntries(TABS.map((t) => [t.value, results.filter((r) => t.types.includes(r.property_type)).length])), [results]);
  const shown = useMemo(() => {
    const types = TABS.find((t) => t.value === tab)!.types;
    const list = results.filter((s) => types.includes(s.property_type)
      && (!stars.length || (s.stars != null && stars.includes(s.stars)))
      && (s.review_score ?? 0) >= minScore
      && amenities.every((a) => hasAmenity(s, a))
      && (!areas.length || areas.includes(s.area))
      && (maxNightly == null || s.nightly_price <= maxNightly));
    const cheapest = Math.min(...list.map((s) => s.nightly_price), Infinity);
    return [...list].sort((a, b) => sort === 'price' ? a.nightly_price - b.nightly_price
      : sort === 'rating' ? (b.review_score ?? 0) - (a.review_score ?? 0)
      : sort === 'distance' ? (a.distance_km ?? 99) - (b.distance_km ?? 99)
      : stayScore(b, cheapest) - stayScore(a, cheapest));
  }, [results, tab, stars, minScore, amenities, areas, maxNightly, sort]);
  const areaNames = [...new Set(results.map((r) => r.area))];
  const filtered = stars.length || minScore || amenities.length || areas.length || maxNightly != null;
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const nights = nightsBetween(trip.start, trip.end);

  return (
    <div className="container page travel-page">
      <TravelHero icon={<Hotel size={13} />} eyebrow="HOTELS & HOMES" title="Find a place to stay" place={trip.destination} art={<Hotel size={64} />}
        subtitle="Hotels, apartments, resorts and hostels compared on price per night, rating, location and what's included."
        tabs={<div className="segmented travel-tablist" role="tablist">{TABS.filter((t) => !data || t.value === 'all' || counts[t.value] > 0 || tab === t.value).map((t) => <button key={t.value} role="tab" aria-selected={tab === t.value} className={tab === t.value ? 'active' : ''} onClick={() => setTab(t.value)}>{t.icon} {t.label}{data ? <small>{counts[t.value]}</small> : null}</button>)}</div>}>
        <form className="travel-form stays-form" onSubmit={search} noValidate>
          <AirportField label="Destination" value={trip.destination} onChange={(a) => setTrip({ destination: a })} />
          <DateField label="Check-in" endLabel="Check-out" start={trip.start} end={trip.end} range onChange={(s, e) => setTrip({ start: s, end: e })} />
          <GuestPicker adults={trip.adults} children={trip.children} rooms={trip.rooms} onChange={(g) => setTrip(g)} />
          <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Search size={16} />} Search stays</button>
        </form>
        {formError && <Notice kind="error">{formError}</Notice>}
      </TravelHero>

      {error && <Notice kind="error">{error}</Notice>}
      {!data && !busy && (
        <div className="card"><EmptyState icon={<BedDouble size={30} />} title="Where are you going?">Choose a destination and dates to compare places to stay.</EmptyState></div>
      )}
      {busy && !data && <Loading label="Finding places to stay…" />}

      {data && (
        <div className={`travel-results ${busy ? 'is-refreshing' : ''}`}>
          <aside className="card travel-filters" aria-label="Filters">
            <div className="filters-title"><b>Filters</b>{filtered ? <button className="link-btn small" onClick={() => { setStars([]); setMinScore(0); setAmenities([]); setAreas([]); setMaxNightly(null); }}>Clear</button> : null}</div>
            {priceCap > 0 && (
              <fieldset className="filter-block"><legend>Max per night</legend>
                <input type="range" min={0} max={priceCap} step={Math.max(1, Math.round(priceCap / 50))} value={maxNightly ?? priceCap} onChange={(e) => setMaxNightly(Number(e.target.value) >= priceCap ? null : Number(e.target.value))} aria-label="Maximum price per night" />
                <div className="range-labels"><span>Any</span><span><Price amount={maxNightly ?? priceCap} currency={results[0].currency} inline /></span></div>
              </fieldset>
            )}
            <fieldset className="filter-block"><legend>Star rating</legend>
              <div className="chip-wrap">{[5, 4, 3, 2].map((n) => <button key={n} className={`chip small ${stars.includes(n) ? 'active' : ''}`} aria-pressed={stars.includes(n)} onClick={() => setStars(toggle(stars, n))}>{n}★</button>)}</div>
            </fieldset>
            <fieldset className="filter-block"><legend>Guest rating</legend>
              <div className="chip-wrap">{[0, 7, 8, 9].map((n) => <button key={n} className={`chip small ${minScore === n ? 'active' : ''}`} aria-pressed={minScore === n} onClick={() => setMinScore(n)}>{n ? `${n}+` : 'Any'}</button>)}</div>
            </fieldset>
            <fieldset className="filter-block"><legend>Popular filters</legend>
              {AMENITY_FILTERS.map((a) => <CheckRow key={a} label={a} count={results.filter((s) => hasAmenity(s, a)).length} checked={amenities.includes(a)} onChange={() => setAmenities(toggle(amenities, a))} />)}
            </fieldset>
            {areaNames.length > 1 && (
              <fieldset className="filter-block"><legend>Area</legend>
                {areaNames.map((a) => <CheckRow key={a} label={a} count={results.filter((s) => s.area === a).length} checked={areas.includes(a)} onChange={() => setAreas(toggle(areas, a))} />)}
              </fieldset>
            )}
          </aside>

          <div className="travel-list">
            <ProviderNotice status={data.data_status} notice={data.notice} />
            <div className="travel-list-head">
              <span><b>{shown.length} {shown.length === 1 ? 'property' : 'properties'}</b> in {data.city.city} · {data.nights} night{data.nights === 1 ? '' : 's'} · {data.adults + data.children} guest{data.adults + data.children === 1 ? '' : 's'}</span>
              <Listbox label="Sort" value={sort} onChange={(v) => setSort(v as Sort)} align="right" options={[
                { value: 'recommended', label: 'Recommended', hint: 'Rating, price and location' }, { value: 'price', label: 'Lowest price' },
                { value: 'rating', label: 'Top rated' }, { value: 'distance', label: 'Closest to centre' },
              ]} />
            </div>
            {shown.length ? shown.map((s, i) => <StayCard key={s.id} stay={s} nights={data.nights} badge={sort === 'recommended' && i === 0 ? 'Best value' : undefined} />) : (
              <div className="card"><EmptyState icon={<Building2 size={28} />} title="No properties match these filters">Try removing a filter or choosing another tab.</EmptyState></div>
            )}
            <div className="cross-sell card">
              <Compass size={18} />
              <span>Planning {data.city.city}? Build a day-by-day plan, find tours or arrange an airport transfer.</span>
              <button className="btn btn-soft" onClick={() => navigate({ page: 'planner', location: data.city.airport })}>Plan trip</button>
              <button className="btn btn-ghost" onClick={() => navigate({ page: 'tours', kind: 'group', location: data.city.airport })}>Tours</button>
              <button className="btn btn-ghost" onClick={() => navigate({ page: 'cars', tab: 'transfers', location: data.city.airport })}><Car size={15} /> Transfer</button>
            </div>
          </div>
        </div>
      )}
      {!data && nights > 30 && <Notice kind="warn">Stays can be searched for up to 30 nights.</Notice>}
    </div>
  );
}

const TYPE_ICON: Record<PropertyType, ReactNode> = { hotel: <Hotel size={34} />, apartment: <Home size={34} />, resort: <Palmtree size={34} />, hostel: <Tent size={34} />, villa: <Home size={34} /> };

export function StayCard({ stay: s, nights, badge, action, extra }: { stay: Stay; nights: number; badge?: string; action?: ReactNode; extra?: ReactNode }) {
  const [broken, setBroken] = useState(false);
  // Keep the card calm: the two most useful flags only.
  const flags = [
    s.free_cancellation && <span key="c" className="good"><ShieldCheck size={13} /> Free cancellation</span>,
    s.breakfast_included && <span key="b" className="good"><Coffee size={13} /> Breakfast</span>,
    s.sleeps && <span key="s">Sleeps {s.sleeps}</span>,
    s.rooms_left && <span key="r" className="warn">{s.rooms_left} left</span>,
  ].filter(Boolean).slice(0, 2);
  return (
    <article className="card stay-card">
      <div className="stay-photo">
        {s.photo_url && !broken
          ? <img src={s.photo_url} alt={s.name} loading="lazy" onError={() => setBroken(true)} />
          : <MediaPhoto kind="stay" q={s.property_type} seed={s.id} icon={TYPE_ICON[s.property_type]} alt={`${PROPERTY_LABEL[s.property_type]} (illustrative)`} />}
        {badge && <span className="badge green stay-badge">{badge}</span>}
      </div>
      <div className="stay-body">
        <div className="stay-kicker"><span className="tag">{PROPERTY_LABEL[s.property_type]}</span><Stars n={s.stars} /></div>
        <h3>{s.name}</h3>
        <small className="muted stay-where"><MapPin size={12} /> {s.area}{s.distance_km != null ? ` · ${s.distance_km} km to centre` : ''}</small>
        <ul className="stay-amenities">
          {s.amenities.slice(0, 3).map((a) => <li key={a}>{a === 'Free Wi-Fi' ? <Wifi size={12} /> : null}{a}</li>)}
          {s.amenities.length > 3 && <li className="more" title={s.amenities.slice(3).join(', ')}>+{s.amenities.length - 3}</li>}
        </ul>
        {flags.length > 0 && <div className="stay-flags">{flags}</div>}
        {extra}
      </div>
      <div className="stay-side">
        {s.review_score != null && (
          <div className="review-score"><span><b>{reviewLabel(s.review_score)}</b>{s.review_count ? <small>{s.review_count.toLocaleString()} reviews</small> : null}</span><strong>{s.review_score.toFixed(1)}</strong></div>
        )}
        <div className="stay-price">
          <small>{nights} night{nights === 1 ? '' : 's'} total</small>
          <Price amount={s.total_price} currency={s.currency} />
          <small className="muted"><Price amount={s.nightly_price} currency={s.currency} inline /> / night</small>
        </div>
        {action}
      </div>
    </article>
  );
}
