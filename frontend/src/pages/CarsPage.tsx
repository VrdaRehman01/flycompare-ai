import { useEffect, useState, type FormEvent } from 'react';
import { ArrowLeftRight, Briefcase, Car, CarFront, ChevronDown, Clock3, Fuel, Gauge, Luggage, MapPin, Plane, Search, ShieldCheck, Star, UserCheck, Users } from 'lucide-react';
import { AirportField } from '../components/AirportField';
import { Listbox } from '../components/Listbox';
import { MediaPhoto } from '../components/MediaPhoto';
import { DateField, Stepper, usePopover } from '../components/Pickers';
import { ProviderNotice, TravelHero, useTrip } from '../components/TravelUI';
import { EmptyState, Loading, Notice, Price, SegmentedControl } from '../components/ui';
import { api, errorText } from '../lib/api';
import { durationLabel } from '../lib/format';
import { navigate, type GroundTab } from '../lib/router';
import type { CarOffer, CarsResponse, TransferOffer, TransfersResponse } from '../lib/travel';

const TIMES = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);
// Photo subject for each transfer vehicle type (a representative model, shown as illustrative).
const VEHICLE_PHOTO: Record<string, string> = {
  'Shared shuttle': 'Airport bus shuttle', 'Private sedan': 'Toyota Camry', 'Private SUV': 'Toyota Land Cruiser',
  'Private minivan': 'Toyota HiAce', 'Business-class sedan': 'Mercedes-Benz E-Class', 'Private minibus': 'Mercedes-Benz Sprinter',
};

export function CarsPage({ tab, location }: { tab: GroundTab; location?: string }) {
  const setTab = (t: GroundTab) => navigate({ page: 'cars', tab: t, location });
  const tabs = (
    <div className="segmented travel-tablist" role="tablist">
      <button role="tab" aria-selected={tab === 'rental'} className={tab === 'rental' ? 'active' : ''} onClick={() => setTab('rental')}><Car size={15} /> Car rental</button>
      <button role="tab" aria-selected={tab === 'transfers'} className={tab === 'transfers' ? 'active' : ''} onClick={() => setTab('transfers')}><Plane size={15} /> Airport transfers</button>
    </div>
  );
  return <div className="container page travel-page">{tab === 'rental' ? <RentalSearch location={location} tabs={tabs} /> : <TransferSearch location={location} tabs={tabs} />}</div>;
}

function TimeSelect({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return <label className="time-select"><span>{label}</span><select value={value} onChange={(e) => onChange(e.target.value)}>{TIMES.map((t) => <option key={t}>{t}</option>)}</select></label>;
}

/* ------------------------------------------------------------- car rental */

function RentalSearch({ location, tabs }: { location?: string; tabs: JSX.Element }) {
  const [trip, setTrip] = useTrip(location);
  const [pickupTime, setPickupTime] = useState('10:00');
  const [dropoffTime, setDropoffTime] = useState('10:00');
  const [age, setAge] = useState(30);
  const [data, setData] = useState<CarsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState('All');
  const [automatic, setAutomatic] = useState(false);
  const [freeCancel, setFreeCancel] = useState(false);
  const [sort, setSort] = useState<'price' | 'rating' | 'seats'>('price');

  const search = (e?: FormEvent) => {
    e?.preventDefault();
    if (!trip.destination) { setError('Choose a pick-up airport.'); return; }
    setError(null); setBusy(true);
    const q = new URLSearchParams({ location: trip.destination.code, pickup_date: trip.start, dropoff_date: trip.end || trip.start, pickup_time: pickupTime, dropoff_time: dropoffTime, driver_age: String(age) });
    api<CarsResponse>(`/api/cars/search?${q}`).then(setData).catch((err) => setError(errorText(err))).finally(() => setBusy(false));
  };
  useEffect(() => { if (trip.destination && !data) search(); }, [trip.destination?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const results = data?.results ?? [];
  const cats = ['All', ...new Set(results.map((r) => r.category))];
  // One card per car class (the cheapest offer) unless a class is chosen, which keeps the page calm.
  const filtered = results.filter((r) => (category === 'All' || r.category === category) && (!automatic || r.transmission === 'Automatic') && (!freeCancel || r.free_cancellation));
  const shown = (category === 'All' ? cats.slice(1).map((c) => filtered.filter((r) => r.category === c).sort((a, b) => a.total_price - b.total_price)[0]).filter(Boolean) : filtered)
    .sort((a, b) => sort === 'rating' ? b.supplier_rating - a.supplier_rating : sort === 'seats' ? b.seats - a.seats || a.total_price - b.total_price : a.total_price - b.total_price);

  return (
    <>
      <TravelHero icon={<CarFront size={13} />} eyebrow="CAR SERVICES" title="Rent a car at the airport" tabs={tabs} place={trip.destination} art={<CarFront size={64} />}
        subtitle="Compare car classes and rental terms: mileage, fuel policy, deposit and where you collect it.">
        <form className="travel-form cars-form" onSubmit={search} noValidate>
          <AirportField label="Pick-up airport" value={trip.destination} onChange={(a) => setTrip({ destination: a })} />
          <DateField label="Pick-up" endLabel="Drop-off" start={trip.start} end={trip.end} range onChange={(s, e) => setTrip({ start: s, end: e })} />
          <div className="time-pair"><TimeSelect label="Pick-up time" value={pickupTime} onChange={setPickupTime} /><TimeSelect label="Drop-off time" value={dropoffTime} onChange={setDropoffTime} /></div>
          <label className="age-field"><span>Driver age</span><input type="number" min={18} max={99} value={age} onChange={(e) => setAge(Math.max(18, Math.min(99, Number(e.target.value) || 18)))} /></label>
          <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Search size={16} />} Search cars</button>
        </form>
      </TravelHero>
      {error && <Notice kind="error">{error}</Notice>}
      {!data && !busy && <div className="card"><EmptyState icon={<Car size={30} />} title="Pick up a car where you land">Choose an airport and your rental dates to compare cars.</EmptyState></div>}
      {busy && !data && <Loading label="Finding cars…" />}
      {data && (
        <div className={`travel-section ${busy ? 'is-refreshing' : ''}`}>
          <ProviderNotice status={data.data_status} notice={data.notice} />
          <div className="results-bar">
            <div className="chip-wrap">{cats.map((c) => <button key={c} className={`chip small ${category === c ? 'active' : ''}`} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}</div>
            <div className="chip-wrap">
              <button className={`chip small ${automatic ? 'active' : ''}`} aria-pressed={automatic} onClick={() => setAutomatic(!automatic)}>Automatic</button>
              <button className={`chip small ${freeCancel ? 'active' : ''}`} aria-pressed={freeCancel} onClick={() => setFreeCancel(!freeCancel)}>Free cancellation</button>
              <Listbox label="Sort" value={sort} onChange={(v) => setSort(v as typeof sort)} align="right" options={[{ value: 'price', label: 'Lowest total' }, { value: 'rating', label: 'Supplier rating' }, { value: 'seats', label: 'Most seats' }]} />
            </div>
          </div>
          <p className="results-caption">{category === 'All' ? `Best price in each class at ${data.airport.name}` : `${shown.length} ${category} offers`} · {data.rental_days} rental day{data.rental_days === 1 ? '' : 's'}. {data.notes.slice(1).join(' ')}</p>
          <div className="tile-grid">
            {shown.map((c) => <CarTile key={c.id} car={c} days={data.rental_days} onMore={category === 'All' ? () => setCategory(c.category) : undefined} />)}
          </div>
          {!shown.length && <div className="card"><EmptyState icon={<Car size={26} />} title="No cars match these filters">Remove a filter to see more cars.</EmptyState></div>}
        </div>
      )}
    </>
  );
}

function CarTile({ car: c, days, onMore }: { car: CarOffer; days: number; onMore?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="card tile">
      <MediaPhoto q={c.model} icon={<CarFront size={46} />} alt={c.model} className="tile-photo" label={<span className="tag solid">{c.category}</span>} />
      <div className="tile-body">
        <h3>{c.model.replace(' or similar', '')} <small>or similar</small></h3>
        <ul className="spec-list">
          <li><Users size={13} /> {c.seats}</li><li><Luggage size={13} /> {c.bags_large + c.bags_small} bags</li><li><Gauge size={13} /> {c.transmission}</li>
        </ul>
        <p className="tile-note">{c.free_cancellation ? <span className="good-text"><ShieldCheck size={13} /> Free cancellation</span> : <span className="muted">Non-refundable</span>} · {c.in_terminal ? 'In terminal' : 'Shuttle to desk'}</p>
        {open && (
          <ul className="tile-details">
            <li><MapPin size={13} /> {c.pickup}</li><li><Fuel size={13} /> Fuel policy: {c.fuel_policy}</li><li><Gauge size={13} /> Mileage: {c.mileage}</li>
            <li><Briefcase size={13} /> Deposit about <Price amount={c.deposit} currency={c.currency} inline /></li>
            <li><ShieldCheck size={13} /> Includes {c.includes.join(', ').toLowerCase()}</li>
          </ul>
        )}
        <div className="tile-foot">
          <span className="tile-price"><small>{days} day{days === 1 ? '' : 's'} · {c.supplier} <Star size={10} /> {c.supplier_rating.toFixed(1)}</small><Price amount={c.total_price} currency={c.currency} /></span>
          <div className="tile-actions">
            <button className="link-btn small" onClick={() => setOpen(!open)} aria-expanded={open}>Details <ChevronDown size={12} className={open ? 'flip' : ''} /></button>
            {onMore && <button className="link-btn small" onClick={onMore}>More {c.category}</button>}
          </div>
        </div>
      </div>
    </article>
  );
}

/* -------------------------------------------------------- airport transfers */

function TransferSearch({ location, tabs }: { location?: string; tabs: JSX.Element }) {
  const [trip, setTrip] = useTrip(location);
  const [direction, setDirection] = useState<'from_airport' | 'to_airport'>('from_airport');
  const [date, setDate] = useState(trip.start);
  const [time, setTime] = useState('12:00');
  const [passengers, setPassengers] = useState(trip.adults + trip.children);
  const [bags, setBags] = useState(trip.adults + trip.children);
  const [data, setData] = useState<TransfersResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<'all' | 'private' | 'shared'>('all');
  const party = usePopover();

  const search = (e?: FormEvent) => {
    e?.preventDefault();
    if (!trip.destination) { setError('Choose the airport.'); return; }
    setError(null); setBusy(true);
    const q = new URLSearchParams({ location: trip.destination.code, date, time, passengers: String(passengers), bags: String(bags), direction });
    api<TransfersResponse>(`/api/transfers/search?${q}`).then(setData).catch((err) => setError(errorText(err))).finally(() => setBusy(false));
  };
  useEffect(() => { if (trip.destination && !data) search(); }, [trip.destination?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = (data?.results ?? []).filter((o) => kind === 'all' || o.kind === kind);
  return (
    <>
      <TravelHero icon={<CarFront size={13} />} eyebrow="CAR SERVICES" title="Airport transfers" tabs={tabs} place={trip.destination} art={<ArrowLeftRight size={64} />}
        subtitle="Private cars and shared shuttles between the airport and the city, with journey time and luggage space.">
        <form className="travel-form transfers-form" onSubmit={search} noValidate>
          <AirportField label="Airport" value={trip.destination} onChange={(a) => setTrip({ destination: a })} />
          <SegmentedControl label="Direction" value={direction} onChange={setDirection} options={[{ value: 'from_airport', label: 'Airport → city' }, { value: 'to_airport', label: 'City → airport' }]} />
          <DateField label={direction === 'from_airport' ? 'Arrival date' : 'Pickup date'} start={date} onChange={(s) => setDate(s)} />
          <TimeSelect label={direction === 'from_airport' ? 'Flight lands' : 'Pickup time'} value={time} onChange={setTime} />
          <div className="popover-wrap" ref={party.ref}>
            <button type="button" className="pill-trigger" aria-expanded={party.open} onClick={() => party.setOpen((v) => !v)}><Users size={14} /><span>{passengers} passenger{passengers === 1 ? '' : 's'} · {bags} bag{bags === 1 ? '' : 's'}</span></button>
            {party.open && (
              <div className="popover card passenger-popover" role="dialog" aria-label="Passengers and bags">
                <Stepper label="Passengers" hint="Including children" value={passengers} min={1} max={14} onChange={setPassengers} />
                <Stepper label="Suitcases" hint="Large bags" value={bags} min={0} max={20} onChange={setBags} />
                <div className="popover-actions"><button type="button" className="btn btn-primary" onClick={() => party.setOpen(false)}>Done</button></div>
              </div>
            )}
          </div>
          <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Search size={16} />} Search</button>
        </form>
      </TravelHero>
      {error && <Notice kind="error">{error}</Notice>}
      {!data && !busy && <div className="card"><EmptyState icon={<ArrowLeftRight size={30} />} title="Get to your hotel without the taxi queue">Choose an airport, date and party size to compare transfers.</EmptyState></div>}
      {busy && !data && <Loading label="Finding transfers…" />}
      {data && (
        <div className={`travel-section ${busy ? 'is-refreshing' : ''}`}>
          <ProviderNotice status={data.data_status} notice={data.notice} />
          <div className="transfer-route card">
            <span><Plane size={16} /> <b>{data.airport.code}</b></span>
            <span className="route-line"><small>{data.distance_km} km · about {durationLabel(data.estimated_minutes)}{data.peak_traffic ? ' in peak traffic' : ''}</small></span>
            <span><MapPin size={16} /> <b>{data.city.city} centre</b></span>
          </div>
          <div className="results-bar">
            <p className="results-caption">{shown.length} options for {data.passengers} passenger{data.passengers === 1 ? '' : 's'} and {data.bags} bag{data.bags === 1 ? '' : 's'}</p>
            <SegmentedControl label="Transfer type" value={kind} onChange={setKind} options={[{ value: 'all', label: 'All' }, { value: 'private', label: 'Private' }, { value: 'shared', label: 'Shared' }]} />
          </div>
          <div className="tile-grid">
            {shown.map((o, i) => <TransferTile key={o.id} offer={o} passengers={data.passengers} cheapest={i === 0 && kind === 'all'} />)}
          </div>
          {!shown.length && <div className="card"><EmptyState icon={<CarFront size={26} />} title="No vehicles fit this party">Try fewer bags or a private minibus.</EmptyState></div>}
        </div>
      )}
    </>
  );
}

function TransferTile({ offer: o, passengers, cheapest }: { offer: TransferOffer; passengers: number; cheapest: boolean }) {
  return (
    <article className="card tile">
      <MediaPhoto q={VEHICLE_PHOTO[o.vehicle] ?? o.vehicle} icon={o.kind === 'shared' ? <Users size={46} /> : <CarFront size={46} />} alt={o.vehicle} className="tile-photo"
        label={<>{cheapest && <span className="badge green">Lowest price</span>}<span className="tag solid">{o.kind === 'shared' ? 'Shared' : 'Private'}</span></>} />
      <div className="tile-body">
        <h3>{o.vehicle}</h3>
        <ul className="spec-list">
          <li><Users size={13} /> {o.max_passengers ? `Up to ${o.max_passengers}` : '1 seat each'}</li>
          <li><Luggage size={13} /> {o.max_passengers ? `${o.max_bags} bags` : '2 bags each'}</li>
          <li><Clock3 size={13} /> {durationLabel(o.duration_minutes)}</li>
        </ul>
        <p className="tile-note">
          {o.meet_and_greet ? <span className="good-text"><UserCheck size={13} /> Meet &amp; greet{o.flight_tracking ? `, ${o.free_waiting_minutes} min free wait` : ''}</span> : <span className="muted">Stops at several hotels</span>}
        </p>
        <div className="tile-foot">
          <span className="tile-price"><small>{o.price_basis === 'per person' ? `${passengers} × ` : ''}{o.supplier} · free cancellation</small><Price amount={o.total_price} currency={o.currency} /></span>
        </div>
      </div>
    </article>
  );
}
