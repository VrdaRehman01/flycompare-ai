import { useMemo, useState, type FormEvent } from 'react';
import { ArrowRight, Armchair, CheckCircle2, Hotel, Info, Package, Plane, Search } from 'lucide-react';
import { AirportField } from '../components/AirportField';
import { Listbox } from '../components/Listbox';
import { DateField } from '../components/Pickers';
import { GuestPicker, ProviderNotice, TravelHero, useConverter, useTrip } from '../components/TravelUI';
import { EmptyState, Loading, Notice, StatusPill } from '../components/ui';
import { AirlineLogo } from '../illustrations';
import { api, errorText } from '../lib/api';
import { durationLabel, legsOf, money, stopsLabel, timeOf } from '../lib/format';
import { scoreResults, sortResults, totalDurationOf } from '../lib/results';
import { nightsBetween, type StaysResponse } from '../lib/travel';
import { CABINS, type AirportRef, type Cabin, type Flight, type SearchForm, type SearchResponse } from '../lib/types';
import { emptyForm, searchBody } from '../lib/validation';
import { StayCard, stayScore } from './StaysPage';

type Pick = { key: 'cheapest' | 'best' | 'fastest'; label: string; flight: Flight };
type Sort = 'value' | 'total' | 'rating';

export function PackagesPage({ location, origin, onOriginChange, onOpenFlight }: {
  location?: string; origin: AirportRef | null; onOriginChange: (a: AirportRef | null) => void; onOpenFlight: (f: Flight, q: SearchForm) => void;
}) {
  const [trip, setTrip] = useTrip(location);
  const [cabin, setCabin] = useState<Cabin>('Economy');
  const [flights, setFlights] = useState<{ res: SearchResponse; form: SearchForm } | null>(null);
  const [stays, setStays] = useState<StaysResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stayError, setStayError] = useState<string | null>(null);
  const [pickKey, setPickKey] = useState<Pick['key']>('best');
  const [sort, setSort] = useState<Sort>('value');
  const [chosenStay, setChosenStay] = useState<string | null>(null);

  const search = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!origin || !trip.destination) { setError('Choose where you are flying from and to.'); return; }
    if (origin.code === trip.destination.code) { setError('Choose a destination different from your departure airport.'); return; }
    if (!trip.start || !trip.end || trip.end <= trip.start) { setError('Choose departure and return dates at least one night apart.'); return; }
    setError(null); setStayError(null); setBusy(true); setChosenStay(null);
    const form: SearchForm = {
      ...emptyForm(origin), destination: trip.destination, departure: trip.start, returnDate: trip.end, cabin,
      passengers: { adults: trip.adults, childAges: Array(trip.children).fill(8), infants: 0 },
    };
    const stayQuery = new URLSearchParams({ location: trip.destination.code, check_in: trip.start, check_out: trip.end, adults: String(trip.adults), children: String(trip.children), rooms: String(trip.rooms) });
    const [f, s] = await Promise.allSettled([
      api<SearchResponse>('/api/flights/search', { method: 'POST', body: searchBody(form) }),
      api<StaysResponse>(`/api/stays/search?${stayQuery}`),
    ]);
    if (f.status === 'fulfilled') setFlights({ res: f.value, form }); else { setFlights(null); setError(errorText(f.reason)); }
    if (s.status === 'fulfilled') setStays(s.value); else { setStays(null); setStayError(errorText(s.reason)); }
    setBusy(false);
  };

  const picks = useMemo<Pick[]>(() => {
    const list = flights?.res.results ?? [];
    if (!list.length) return [];
    const scores = scoreResults(list);
    const out: Pick[] = [
      { key: 'best', label: 'Best overall', flight: sortResults(list, 'recommended', scores)[0] },
      { key: 'cheapest', label: 'Cheapest', flight: sortResults(list, 'cheapest', scores)[0] },
      { key: 'fastest', label: 'Fastest', flight: [...list].sort((a, b) => totalDurationOf(a) - totalDurationOf(b))[0] },
    ];
    return out;
  }, [flights]);
  const pick = picks.find((p) => p.key === pickKey) ?? picks[0];
  const flight = pick?.flight;
  const conv = useConverter(flight?.currency ?? 'USD');
  const flightPrice = flight ? conv.to(flight.price, flight.currency) : null;

  const packages = useMemo(() => {
    const list = stays?.results ?? [];
    const cheapest = Math.min(...list.map((s) => s.nightly_price), Infinity);
    const rows = list.map((s) => {
      const stayPrice = conv.to(s.total_price, s.currency);
      return { stay: s, stayPrice, total: stayPrice != null && flightPrice != null ? stayPrice + flightPrice : null, value: stayScore(s, cheapest) };
    });
    return rows.sort((a, b) => sort === 'total' ? (a.total ?? Infinity) - (b.total ?? Infinity)
      : sort === 'rating' ? (b.stay.review_score ?? 0) - (a.stay.review_score ?? 0) : b.value - a.value);
  }, [stays, flightPrice, sort, conv]);
  const selected = packages.find((p) => p.stay.id === chosenStay) ?? packages[0];
  const travellers = trip.adults + trip.children;
  const nights = stays?.nights ?? nightsBetween(trip.start, trip.end);
  const approx = (flight && flight.currency !== conv.currency) || (selected && selected.stay.currency !== conv.currency);

  return (
    <div className="container page travel-page">
      <TravelHero icon={<Package size={13} />} eyebrow="FLIGHT & HOTEL" title="Build a flight and hotel package" place={trip.destination} art={<Package size={64} />}
        subtitle="Search flights and stays together, then see the full trip cost for every hotel with your chosen flight.">
        <form className="travel-form packages-form" onSubmit={search} noValidate>
          <AirportField label="From" value={origin} exclude={trip.destination?.code} onChange={onOriginChange} />
          <AirportField label="To" value={trip.destination} exclude={origin?.code} onChange={(a) => setTrip({ destination: a })} />
          <DateField label="Depart" endLabel="Return" start={trip.start} end={trip.end} range onChange={(s, e) => setTrip({ start: s, end: e })} />
          <div className="travel-form-pills">
            <GuestPicker adults={trip.adults} children={trip.children} rooms={trip.rooms} maxAdults={9} onChange={(g) => setTrip(g)} />
            <Listbox label="Cabin" icon={<Armchair size={14} />} value={cabin} onChange={(c) => setCabin(c as Cabin)} options={CABINS.map((c) => ({ value: c, label: c }))} />
          </div>
          <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Search size={16} />} Search packages</button>
        </form>
        {busy && <p className="muted small">Searching flights and stays at the same time. Flight search can take up to 30 seconds…</p>}
      </TravelHero>

      {error && <Notice kind="error">{error}</Notice>}
      {!flights && !busy && !error && (
        <div className="card"><EmptyState icon={<Package size={30} />} title="Your trip, priced in one place">Choose your route, dates and travellers. We compare flights and stays, then add them up for you.</EmptyState></div>
      )}
      {busy && !flights && <Loading label="Building packages…" />}

      {flights && (
        <div className={`package-layout ${busy ? 'is-refreshing' : ''}`}>
          <div className="package-main">
            <section className="package-step">
              <h2><span className="step-num">1</span> Choose your flight <StatusPill status={flights.res.data_status} /></h2>
              {picks.length ? (
                <div className="flight-picks" role="radiogroup" aria-label="Flight">
                  {picks.map((p) => {
                    const legs = legsOf(p.flight);
                    return (
                      <button key={p.key} role="radio" aria-checked={pick?.key === p.key} className={`card flight-pick ${pick?.key === p.key ? 'active' : ''}`} onClick={() => setPickKey(p.key)}>
                        <span className="pick-label">{pick?.key === p.key && <CheckCircle2 size={14} />} {p.label}</span>
                        <span className="pick-airline"><AirlineLogo name={p.flight.airline} src={p.flight.airline_logo_url} size={28} /> {p.flight.airline}</span>
                        {legs.map((l, i) => (
                          <span key={i} className="pick-leg"><b>{timeOf(l.departing_at)}</b> {l.origin} <ArrowRight size={11} /> <b>{timeOf(l.arriving_at)}</b> {l.destination}<small>{durationLabel(l.duration_minutes)} · {stopsLabel(l.stops)}</small></span>
                        ))}
                        <strong>{money(p.flight.price, p.flight.currency)}</strong>
                      </button>
                    );
                  })}
                </div>
              ) : <Notice kind="warn">No flights were found for these dates. Try other dates or a nearby airport.</Notice>}
              {flight && <button className="link-btn small" onClick={() => onOpenFlight(flight, flights.form)}>View full flight itinerary, bags and fare rules <ArrowRight size={12} /></button>}
            </section>

            <section className="package-step">
              <div className="package-step-head">
                <h2><span className="step-num">2</span> Choose your stay</h2>
                <Listbox label="Sort packages" value={sort} onChange={(v) => setSort(v as Sort)} align="right" options={[
                  { value: 'value', label: 'Best value' }, { value: 'total', label: 'Lowest package total' }, { value: 'rating', label: 'Top rated stay' },
                ]} />
              </div>
              {stayError && <Notice kind="error">{stayError}</Notice>}
              {stays && <ProviderNotice status={stays.data_status} notice={stays.notice} />}
              {packages.slice(0, 12).map((p, i) => (
                <StayCard key={p.stay.id} stay={p.stay} nights={nights} badge={i === 0 ? (sort === 'total' ? 'Lowest total' : sort === 'rating' ? 'Top rated' : 'Best value') : undefined}
                  extra={<div className="package-line"><Package size={13} /> Trip total with your flight <b>{p.total != null ? `${approx ? '≈ ' : ''}${money(p.total, conv.currency)}` : 'converting…'}</b>{p.total != null && travellers > 1 ? <small> · {money(p.total / travellers, conv.currency)} per traveller</small> : null}</div>}
                  action={<button className={`btn ${selected?.stay.id === p.stay.id ? 'btn-primary' : 'btn-soft'}`} onClick={() => setChosenStay(p.stay.id)}>{selected?.stay.id === p.stay.id ? 'Selected' : 'Choose'}</button>} />
              ))}
            </section>
          </div>

          <aside className="card package-summary" aria-label="Package summary">
            <h3>Your package</h3>
            {flight ? (
              <div className="sum-row"><Plane size={15} /><span><b>{flight.airline}</b><small>{pick?.label} · round trip · {travellers} traveller{travellers === 1 ? '' : 's'}</small></span><strong>{money(flight.price, flight.currency)}</strong></div>
            ) : <p className="muted small">Choose a flight.</p>}
            {selected ? (
              <div className="sum-row"><Hotel size={15} /><span><b>{selected.stay.name}</b><small>{nights} night{nights === 1 ? '' : 's'} · {trip.rooms} room{trip.rooms === 1 ? '' : 's'}</small></span><strong>{money(selected.stay.total_price, selected.stay.currency)}</strong></div>
            ) : <p className="muted small">Choose a stay.</p>}
            <div className="sum-total">
              <span>Package total{approx ? ` (≈ ${conv.currency})` : ''}</span>
              <strong>{selected?.total != null ? money(selected.total, conv.currency) : '—'}</strong>
              {selected?.total != null && travellers > 1 && <small>{money(selected.total / travellers, conv.currency)} per traveller</small>}
            </div>
            <div className="sum-pills"><span>Flight</span><StatusPill status={flights.res.data_status} />{stays && <><span>Stay</span><StatusPill status={stays.data_status} /></>}</div>
            {flight && <button className="btn btn-primary full" onClick={() => onOpenFlight(flight, flights.form)}>Continue with this flight</button>}
            <p className="muted small"><Info size={12} /> Flight and stay are priced separately by each provider and added together here; no bundle discount is assumed.{approx ? ' Amounts in other currencies are converted at reference rates.' : ''} FlyCompare compares offers and does not sell them.</p>
          </aside>
        </div>
      )}
    </div>
  );
}
