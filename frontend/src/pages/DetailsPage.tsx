import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Armchair, BadgeCheck, Briefcase, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock3, ExternalLink, Heart, Info, Leaf,
  Luggage, Minus, Plane, PlaneLanding, PlaneTakeoff, Plug, Plus, RefreshCw, ShieldCheck, Utensils, Wifi,
} from 'lucide-react';
import { refundText, SegmentList, type DetailsTab } from '../components/FlightCard';
import { LazyWorldMap } from '../components/LazyMap';
import { SeatMap, type SeatChoice } from '../components/SeatMap';
import { api, errorText } from '../lib/api';
import { passengerSummary } from '../lib/validation';
import { Loading, Notice, Price, StatusPill } from '../components/ui';
import { AirlineLogo } from '../illustrations';
import { bagText, cityOf, dayOffset, durationLabel, knownAirport, legsOf, minutesBetween, money, rememberAirports, relativeTime, shortDate, stopsLabel, timeOf, toRef } from '../lib/format';
import { navigate, readSession, writeSession } from '../lib/router';
import { totalDurationOf } from '../lib/results';
import type { Airport, AirportRef, Amenity, Baggage, FareCondition, Flight, OfferDetails, SearchForm, Segment, SeatMapResponse } from '../lib/types';
import { useAuth } from '../state';

const TABS: DetailsTab[] = ['Baggage', 'Fare conditions', 'Aircraft', 'Amenities', 'Seats'];
const NOT_SUPPLIED = 'Not supplied by this provider';

/** Refund/change status exactly as supplied: unknown is never shown as "not allowed". */
export function conditionStatus(c: FareCondition | null | undefined, kind: 'refund' | 'change'): { label: string; tone: 'good' | 'warn' | 'bad' | 'unknown'; detail: string } {
  const noun = kind === 'refund' ? 'Refund' : 'Changes';
  if (!c || c.allowed == null) return { label: 'Unknown', tone: 'unknown', detail: `${noun} terms were not supplied by the provider.` };
  if (!c.allowed) return { label: kind === 'refund' ? 'Non-refundable' : 'Changes not allowed', tone: 'bad', detail: `${noun} before departure is not permitted on this fare.` };
  if (c.penalty_amount == null) return { label: kind === 'refund' ? 'Refundable' : 'Changes allowed', tone: 'warn', detail: 'Allowed; the fee was not supplied.' };
  if (c.penalty_amount === 0) return { label: kind === 'refund' ? 'Refundable' : 'Changes allowed', tone: 'good', detail: 'Allowed with no penalty.' };
  return { label: kind === 'refund' ? 'Refundable with fee' : 'Changes allowed with fee', tone: 'warn', detail: `Penalty ${money(c.penalty_amount, c.penalty_currency ?? 'USD', 2)} per the provider (plus any fare difference).` };
}

const amenityText = (a: Amenity | null | undefined, name: string) => {
  if (!a || a.available == null) return { text: 'Unknown', tone: 'unknown' as const };
  if (!a.available) return { text: `No ${name}`, tone: 'bad' as const };
  return { text: a.cost ? `${name[0].toUpperCase()}${name.slice(1)} · ${a.cost}` : `${name[0].toUpperCase()}${name.slice(1)} available`, tone: 'good' as const };
};

const MANUFACTURERS = ['Airbus', 'Boeing', 'Embraer', 'ATR', 'Bombardier', 'De Havilland', 'Comac', 'Sukhoi', 'McDonnell Douglas', 'Fokker', 'Saab', 'Cessna'];
/** Manufacturer only when the provider's aircraft name starts with it; never guessed. */
const manufacturerOf = (name: string) => MANUFACTURERS.find((m) => name.toLowerCase().startsWith(m.toLowerCase())) ?? null;

export function DetailsPage({ flight: f, query, hasResults }: { flight: Flight; query: SearchForm | null; hasResults: boolean }) {
  const { isSaved, toggleSaved } = useAuth();
  const [tab, setTab] = useState<DetailsTab>(() => {
    const wanted = readSession<DetailsTab>('fc-details-tab');
    writeSession('fc-details-tab', null);
    return wanted && TABS.includes(wanted) ? wanted : 'Baggage';
  });
  const [open, setOpen] = useState<number[]>([0, 1]);
  const [offer, setOffer] = useState<{ state: 'idle' | 'loading' | 'done' | 'error'; data?: OfferDetails; error?: string }>({ state: 'idle' });
  const [bags, setBags] = useState<Record<string, number>>({});
  const [seats, setSeats] = useState<SeatChoice[]>([]);
  const legs = legsOf(f);
  const pax = query?.passengers ?? null;
  const paxText = pax ? passengerSummary(pax) : f.passenger_count ? `${f.passenger_count} passenger${f.passenger_count > 1 ? 's' : ''}` : 'travellers as searched';
  const stops = useItineraryStops(f);
  const saved = isSaved(f.id);
  const segments = legs.flatMap((l) => l.segments);
  const cabinName = segments.find((s) => s.cabin_marketing_name)?.cabin_marketing_name ?? f.cabin;

  const loadOffer = () => {
    if (!f.supports_extra_services || offer.state === 'loading') return;
    setOffer({ state: 'loading', data: offer.data });
    api<OfferDetails>(`/api/flights/offers/${encodeURIComponent(f.id)}`)
      .then((data) => setOffer({ state: 'done', data }))
      .catch((err) => setOffer({ state: 'error', error: errorText(err) }));
  };
  // Re-check once when extras are first needed (Baggage or Seats tab), never on page load for other tabs.
  useEffect(() => { if ((tab === 'Baggage' || tab === 'Seats') && offer.state === 'idle') loadOffer(); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = offer.data?.supported ? offer.data : null;
  const total = current?.total_amount ?? f.price;
  const currency = current?.total_currency ?? f.currency;
  const bagServices = current?.baggage_services ?? [];
  const extras = [
    ...bagServices.filter((b) => bags[b.id]).map((b) => ({ label: `${bags[b.id]} × extra ${b.bag_type === 'carry_on' ? 'cabin' : 'checked'} bag${b.maximum_weight_kg ? ` (${b.maximum_weight_kg} kg)` : ''}`, amount: (b.amount ?? 0) * bags[b.id], currency: b.currency })),
    ...seats.filter((s) => s.amount).map((s) => ({ label: `Seat ${s.designator}`, amount: s.amount ?? 0, currency: s.currency })),
  ];
  const extrasSameCurrency = extras.every((e) => e.currency === currency);
  const extrasTotal = extras.reduce((sum, e) => sum + e.amount, 0);
  const passengerLabel = (id: string) => {
    const list = current?.passengers ?? [];
    const i = list.findIndex((p) => p.id === id);
    const p = list[i];
    return p ? `Passenger ${i + 1}${p.type ? ` · ${p.type.replace('_', ' ')}` : p.age != null ? ` · age ${p.age}` : ''}` : 'Passenger';
  };

  return (
    <div className="container page details">
      <div className="breadcrumb">
        <button onClick={() => navigate({ page: hasResults ? 'results' : 'home' })}><ChevronLeft size={14} /> {hasResults ? 'Search results' : 'Flights'}</button><ChevronRight size={13} /><span>Flight details</span>
      </div>
      <div className="details-layout">
        <div className="card details-card">
          <div className="details-head">
            <AirlineLogo name={f.airline} size={56} src={f.airline_logo_url} />
            <div className="details-title">
              <h1>{f.airline}</h1>
              <small>{f.flight_number} · {cabinName} · {legs.length > 2 ? 'Multi-city' : legs.length > 1 ? 'Round trip' : 'One way'} · {durationLabel(totalDurationOf(f))} total flying time</small>
              <div className="details-tags">
                <StatusPill status={f.data_status} />
                <span className="badge soft">{f.provider} · retrieved {relativeTime(f.retrieved_at)}</span>
                {legs[0]?.fare_brand_name && <span className="badge soft">Fare: {legs[0].fare_brand_name}</span>}
              </div>
            </div>
            <button className={`btn ${saved ? 'btn-soft' : 'btn-primary'} details-save`} onClick={() => void toggleSaved(f, query)} aria-pressed={saved}><Heart size={15} className={saved ? 'filled' : ''} /> {saved ? 'Saved' : 'Save flight'}</button>
          </div>

          {legs.map((leg, i) => {
            const isOpen = open.includes(i);
            const offset = dayOffset(leg.departing_at, leg.arriving_at);
            const connections = leg.segments.slice(0, -1).map((s, j) => ({ code: s.destination, wait: minutesBetween(s.arriving_at, leg.segments[j + 1].departing_at) }));
            return (
              <section key={i} className="leg-card">
                <div className="leg-card-head">
                  <span className="leg-icon">{i === 0 ? <PlaneTakeoff size={16} /> : <PlaneLanding size={16} />}</span>
                  <div><b>{legs.length > 2 ? `Flight ${i + 1}` : legs.length > 1 ? (i === 0 ? 'Outbound flight' : 'Return flight') : 'Flight'}</b><small>{shortDate(leg.departing_at)} · {cityOf(leg.origin)} to {cityOf(leg.destination)}</small></div>
                  <button className="expand" onClick={() => setOpen(isOpen ? open.filter((x) => x !== i) : [...open, i])} aria-expanded={isOpen}>{isOpen ? 'Hide segments' : 'Show segments'} <ChevronDown size={14} className={isOpen ? 'flip' : ''} /></button>
                </div>
                <div className="leg-overview">
                  <div className="leg-point"><strong>{timeOf(leg.departing_at)}</strong><b>{cityOf(leg.origin)}</b><small>{leg.origin}{leg.segments[0]?.origin_terminal ? ` · Terminal ${leg.segments[0].origin_terminal}` : ''}</small></div>
                  <div className="leg-mid"><small>{durationLabel(leg.duration_minutes)}</small><span className="line"><i /><Plane size={13} /></span><small>{stopsLabel(leg.stops)}</small></div>
                  <div className="leg-point"><strong>{timeOf(leg.arriving_at)}{offset > 0 && <sup>+{offset}</sup>}</strong><b>{cityOf(leg.destination)}</b><small>{leg.destination}{leg.segments.at(-1)?.destination_terminal ? ` · Terminal ${leg.segments.at(-1)!.destination_terminal}` : ''}{offset > 0 ? ` · ${shortDate(leg.arriving_at)}` : ''}</small></div>
                  <div className="leg-meta">
                    {connections.length ? connections.map((c) => <span key={c.code}><Clock3 size={12} /> {durationLabel(c.wait)} in {c.code}</span>) : <span>No connections</span>}
                    {leg.segments.some((s) => s.technical_stops?.length) && <span>Technical stop: {leg.segments.flatMap((s) => s.technical_stops ?? []).join(', ')}</span>}
                    <span>{leg.segments.map((s) => s.flight_number).filter(Boolean).join(' · ') || f.flight_number}</span>
                  </div>
                </div>
                {isOpen && <div className="segments"><SegmentList leg={leg} fallbackAirline={f.airline} fallbackNumber={f.flight_number} /></div>}
              </section>
            );
          })}

          {stops.length > 1 && (
            <div className="details-map">
              <LazyWorldMap route={{ stops }} showAirports={false} height={300} caption="Map of this itinerary" />
            </div>
          )}

          <div className="detail-tabs" role="tablist" aria-label="Flight information">
            {TABS.map((t) => <button key={t} role="tab" id={`tab-${t}`} aria-controls="details-panel" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}
          </div>
          <div className="tab-body" role="tabpanel" id="details-panel" aria-labelledby={`tab-${tab}`}>
            {tab === 'Baggage' && <BaggageTab f={f} legs={legs.length} offer={offer} bags={bags} setBags={setBags} onRetry={loadOffer} />}
            {tab === 'Fare conditions' && <ConditionsTab f={f} />}
            {tab === 'Aircraft' && <AircraftTab segments={segments} />}
            {tab === 'Amenities' && <AmenitiesTab segments={segments} />}
            {tab === 'Seats' && <SeatsTab f={f} passengers={current?.passengers?.map((p) => p.id) ?? []} offerState={offer.state} passengerLabel={passengerLabel} seats={seats} setSeats={setSeats} />}
          </div>
          <div className="disclaimer"><BadgeCheck size={15} />{f.disclaimer} FlyCompare compares offers and does not sell or issue tickets.</div>
        </div>

        <aside className="card fare-summary" aria-label="Fare summary">
          <h2>Fare summary</h2>
          <dl>
            {f.base_amount != null && <><dt>Base fare</dt><dd>{money(f.base_amount, f.base_currency ?? f.currency, 2)}</dd></>}
            {f.tax_amount != null && <><dt>Taxes and fees</dt><dd>{money(f.tax_amount, f.tax_currency ?? f.currency, 2)}</dd></>}
            {f.base_amount == null && <dd className="full muted small">Detailed fare breakdown not supplied by provider.</dd>}
            <dt className="strong">Fare total</dt><dd className="strong">{money(total, currency, 2)}</dd>
            <dd className="full muted small">For {paxText}, all taxes the provider included.</dd>
            {extras.map((e, i) => <Fragment key={i}><dt>{e.label}</dt><dd>{money(e.amount, e.currency ?? currency, 2)}</dd></Fragment>)}
          </dl>
          {extras.length > 0 && (extrasSameCurrency
            ? <div className="fare-total"><span>Total with selected extras</span><Price amount={total + extrasTotal} currency={currency} digits={2} /></div>
            : <Notice kind="warn">Extras are priced in a different currency, so they are not added to the fare total.</Notice>)}
          {extras.length === 0 && <div className="fare-total"><span>Total</span><Price amount={total} currency={currency} digits={2} /></div>}
          {current && current.total_amount != null && Math.abs(current.total_amount - f.price) > 0.005 && (
            <Notice kind="warn">Price changed since your search: was {money(f.price, f.currency, 2)}, now {money(current.total_amount, current.total_currency ?? f.currency, 2)}.</Notice>
          )}
          <div className="fare-meta">
            {current?.checked_at ? <span><RefreshCw size={12} /> Price re-checked {relativeTime(current.checked_at)}</span> : <span><Clock3 size={12} /> Price from search, {relativeTime(f.retrieved_at)}</span>}
            {(current?.expires_at ?? f.expires_at) && <span><CalendarDays size={12} /> Offer expires {relativeTime(current?.expires_at ?? f.expires_at!)}</span>}
            {f.total_emissions_kg != null && <span><Leaf size={12} /> {Math.round(f.total_emissions_kg)} kg CO₂e (provider estimate)</span>}
          </div>
          {f.supports_extra_services && <button className="btn btn-ghost small" onClick={loadOffer} disabled={offer.state === 'loading'}>{offer.state === 'loading' ? <span className="spinner dark" /> : <RefreshCw size={14} />} Re-check price</button>}
          {offer.state === 'error' && <Notice kind="error">{offer.error}</Notice>}
          <p className="muted small">{f.data_status === 'live' ? 'Seats and bags are reserved only when booked with the airline or an agent. FlyCompare does not issue tickets.' : 'Sandbox or demo offer: not bookable.'}</p>
          {(current?.conditions_of_carriage_url ?? f.conditions_of_carriage_url) && <a className="link-btn small" href={(current?.conditions_of_carriage_url ?? f.conditions_of_carriage_url)!} target="_blank" rel="noreferrer noopener"><ExternalLink size={13} /> Airline conditions of carriage</a>}
        </aside>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ tabs */

function BaggageTab({ f, legs, offer, bags, setBags, onRetry }: {
  f: Flight; legs: number; offer: { state: string; data?: OfferDetails; error?: string }; bags: Record<string, number>;
  setBags: (fn: (b: Record<string, number>) => Record<string, number>) => void; onRetry: () => void;
}) {
  const included = f.baggage_allowances ?? [];
  const groups = useMemo(() => {
    const out = new Map<string, Baggage[]>();
    for (const b of included) {
      const key = b.slice_index == null ? 'All flights' : legs > 2 ? `Flight ${b.slice_index + 1}` : legs > 1 ? (b.slice_index === 0 ? 'Outbound' : 'Return') : 'This flight';
      out.set(key, [...(out.get(key) ?? []), b]);
    }
    return [...out];
  }, [included, legs]);
  const services = offer.data?.supported ? offer.data.baggage_services ?? [] : [];
  return (
    <>
      <h3 className="tab-h">Included in this fare</h3>
      {!included.length && !f.baggage_kg && <div className="empty-inline"><Info size={16} /> Baggage information was not supplied by this provider. This does not mean no bags are included — check with the airline.</div>}
      {!included.length && f.baggage_kg != null && <div className="info-grid"><InfoTile icon={<Luggage size={18} />} title="Checked baggage" lines={[`${f.baggage_kg} kg (demo data)`]} /></div>}
      {groups.map(([label, list]) => {
        const byType = (t: string) => list.filter((b) => b.baggage_type === t);
        const describe = (t: string) => byType(t).length ? byType(t).map((b) => `${bagText(b)}${b.passenger_type ? ` · ${b.passenger_type.replace('_', ' ')}` : ''}`) : [NOT_SUPPLIED];
        return (
          <div key={label} className="bag-group">
            {groups.length > 1 && <b className="bag-group-title">{label}</b>}
            <div className="info-grid">
              <InfoTile icon={<Luggage size={18} />} title="Checked baggage" lines={describe('checked')} />
              <InfoTile icon={<Briefcase size={18} />} title="Cabin baggage" lines={describe('carry_on')} />
            </div>
          </div>
        );
      })}
      {included.length > 0 && <p className="muted small tab-note">The provider supplies the number of bags per passenger. Weight and size limits follow the airline's policy{f.conditions_of_carriage_url ? '' : ' and were not included in this offer'}.</p>}

      <h3 className="tab-h">Additional bags</h3>
      {!f.supports_extra_services && <div className="empty-inline"><Info size={16} /> This provider does not offer paid extra baggage through FlyCompare.</div>}
      {f.supports_extra_services && offer.state === 'loading' && <Loading label="Checking extra baggage options with the airline…" />}
      {offer.state === 'error' && <Notice kind="error">{offer.error} <button className="link-btn small" onClick={onRetry}>Try again</button></Notice>}
      {offer.state === 'done' && offer.data?.supported && !services.length && <div className="empty-inline"><Info size={16} /> The airline does not sell extra bags for this offer through the provider.</div>}
      {services.length > 0 && (
        <ul className="extra-list">
          {services.map((s) => {
            const qty = bags[s.id] ?? 0;
            const size = [s.maximum_length_cm, s.maximum_height_cm, s.maximum_depth_cm].every((v) => v != null) ? `${s.maximum_length_cm} × ${s.maximum_height_cm} × ${s.maximum_depth_cm} cm` : null;
            return (
              <li key={s.id}>
                <Luggage size={18} />
                <div><b>Extra {s.bag_type === 'carry_on' ? 'cabin' : 'checked'} bag{s.maximum_weight_kg ? ` · up to ${s.maximum_weight_kg} kg` : ''}</b><small>{size ?? 'Size limit not supplied'} · {s.passenger_ids.length > 1 ? `${s.passenger_ids.length} passengers` : 'per passenger'} · {s.segment_ids.length} flight{s.segment_ids.length === 1 ? '' : 's'}</small></div>
                <span className="extra-price">{s.amount != null ? money(s.amount, s.currency ?? f.currency, 2) : 'Price not supplied'}</span>
                <div className="stepper" aria-label="Quantity">
                  <button onClick={() => setBags((b) => ({ ...b, [s.id]: Math.max(0, qty - 1) }))} disabled={!qty} aria-label="Remove one"><Minus size={14} /></button>
                  <span aria-live="polite">{qty}</span>
                  <button onClick={() => setBags((b) => ({ ...b, [s.id]: Math.min(s.maximum_quantity ?? 1, qty + 1) }))} disabled={qty >= (s.maximum_quantity ?? 1) || s.amount == null} aria-label="Add one"><Plus size={14} /></button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

function ConditionsTab({ f }: { f: Flight }) {
  const refund = f.conditions?.refund_before_departure ? conditionStatus(f.conditions.refund_before_departure, 'refund')
    : f.refundable != null ? { label: refundText(f.refundable), tone: f.refundable ? 'good' : 'bad', detail: 'As supplied by the provider.' } as const : conditionStatus(null, 'refund');
  const change = conditionStatus(f.conditions?.change_before_departure, 'change');
  const legs = legsOf(f);
  const perk = (v: boolean | null | undefined) => (v == null ? 'Unknown' : v ? 'Included' : 'Not included');
  return (
    <>
      <div className="condition-grid">
        <ConditionCard icon={<ShieldCheck size={18} />} title="Refund before departure" status={refund} />
        <ConditionCard icon={<CalendarDays size={18} />} title="Change before departure" status={change} />
      </div>
      {legs.some((l) => l.fare_brand_name || l.priority_boarding != null || l.priority_check_in != null || l.advance_seat_selection != null) && (
        <table className="facts">
          <thead><tr><th>Journey</th><th>Fare brand</th><th>Priority check-in</th><th>Priority boarding</th><th>Advance seat selection</th></tr></thead>
          <tbody>{legs.map((l, i) => <tr key={i}><td>{l.origin} → {l.destination}</td><td>{l.fare_brand_name ?? 'Unknown'}</td><td>{perk(l.priority_check_in)}</td><td>{perk(l.priority_boarding)}</td><td>{perk(l.advance_seat_selection)}</td></tr>)}</tbody>
        </table>
      )}
      <p className="muted small tab-note">Conditions apply to the whole booking as supplied by {f.provider}. "Unknown" means the provider did not say — it does not mean the option is unavailable. Full ticket rules are set by the airline{f.conditions_of_carriage_url ? <> (<a href={f.conditions_of_carriage_url} target="_blank" rel="noreferrer noopener">conditions of carriage</a>)</> : ''}.</p>
    </>
  );
}

function ConditionCard({ icon, title, status }: { icon: ReactNode; title: string; status: { label: string; tone: string; detail: string } }) {
  return <div className={`condition-card ${status.tone}`}><span className="icon-square">{icon}</span><div><small>{title}</small><b>{status.label}</b><small>{status.detail}</small></div></div>;
}

function AircraftTab({ segments }: { segments: Segment[] }) {
  if (!segments.some((s) => s.aircraft)) return <div className="empty-inline"><Info size={16} /> Aircraft type was not supplied by this provider.</div>;
  return (
    <table className="facts">
      <thead><tr><th>Flight</th><th>Route</th><th>Aircraft</th><th>Manufacturer</th><th>Type code</th><th>Operated by</th></tr></thead>
      <tbody>
        {segments.map((s, i) => (
          <tr key={i}>
            <td>{s.flight_number ?? '—'}</td><td>{s.origin} → {s.destination}</td>
            <td>{s.aircraft ?? 'Not supplied'}</td><td>{s.aircraft ? manufacturerOf(s.aircraft) ?? 'Not supplied' : '—'}</td>
            <td>{s.aircraft_code ?? '—'}</td><td>{s.operating_airline ?? s.airline ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AmenitiesTab({ segments }: { segments: Segment[] }) {
  const Status = ({ v }: { v: { text: string; tone: string } }) => <span className={`amenity ${v.tone}`}>{v.text}</span>;
  return (
    <>
      <table className="facts amenities">
        <thead><tr><th>Flight</th><th><Wifi size={13} /> Wi-Fi</th><th><Plug size={13} /> Power</th><th><Armchair size={13} /> Seat</th><th><Utensils size={13} /> Meals</th></tr></thead>
        <tbody>
          {segments.map((s, i) => {
            const seat = s.amenities?.seat;
            const seatText = seat && (seat.type || seat.pitch || seat.legroom) ? [seat.type, seat.pitch ? `${seat.pitch}" pitch` : null, seat.legroom ? `${seat.legroom} legroom` : null].filter(Boolean).join(' · ') : null;
            return (
              <tr key={i}>
                <td>{s.flight_number ?? `${s.origin} → ${s.destination}`}<small className="muted"> {s.cabin_marketing_name ?? s.cabin?.replace('_', ' ') ?? ''}</small></td>
                <td><Status v={amenityText(s.amenities?.wifi, 'Wi-Fi')} /></td>
                <td><Status v={amenityText(s.amenities?.power, 'power')} /></td>
                <td>{seatText ? <span className="amenity good">{seatText}</span> : <Status v={{ text: 'Unknown', tone: 'unknown' }} />}</td>
                <td><Status v={{ text: 'Unknown', tone: 'unknown' }} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted small tab-note">Meals and in-flight entertainment are not part of the flight data this provider supplies, so they are shown as Unknown rather than "not included".</p>
    </>
  );
}

function SeatsTab({ f, passengers, offerState, passengerLabel, seats, setSeats }: {
  f: Flight; passengers: string[]; offerState: string; passengerLabel: (id: string) => string; seats: SeatChoice[]; setSeats: (fn: (s: SeatChoice[]) => SeatChoice[]) => void;
}) {
  const [data, setData] = useState<{ state: 'loading' | 'done' | 'error'; res?: SeatMapResponse; error?: string }>({ state: 'loading' });
  const [segment, setSegment] = useState(0);
  useEffect(() => {
    if (!f.supports_seat_maps) return;
    let live = true;
    api<SeatMapResponse>(`/api/flights/offers/${encodeURIComponent(f.id)}/seat-maps`)
      .then((res) => { if (live) setData({ state: 'done', res }); })
      .catch((err) => { if (live) setData({ state: 'error', error: errorText(err) }); });
    return () => { live = false; };
  }, [f.id, f.supports_seat_maps]);

  if (!f.supports_seat_maps) return <div className="empty-inline"><Info size={16} /> Seat selection is not available for this offer through the current provider.</div>;
  if (data.state === 'loading' || offerState === 'loading') return <Loading label="Loading the seat map from the airline…" />;
  if (data.state === 'error') return <Notice kind="error">{data.error}</Notice>;
  const maps = data.res?.seat_maps ?? [];
  if (!data.res?.supported || !maps.length) return <div className="empty-inline"><Info size={16} /> {data.res?.message ?? 'Seat selection is not available for this offer through the current provider.'}</div>;
  const segs = legsOf(f).flatMap((l) => l.segments);
  const labelFor = (id: string | null, i: number) => { const s = segs.find((x) => x.id === id); return s ? `${s.origin} → ${s.destination}${s.flight_number ? ` · ${s.flight_number}` : ''}` : `Flight ${i + 1}`; };
  // Passengers from the re-checked offer; otherwise those the seat prices are quoted for.
  const ids = passengers.length ? passengers : [...new Set(maps.flatMap((m) => m.cabins.flatMap((c) => c.rows.flat(2).flatMap((e) => ('services' in e ? e.services.map((x) => x.passenger_id) : [])))))];
  const map = maps[Math.min(segment, maps.length - 1)];
  return (
    <>
      {maps.length > 1 && <div className="seg-switch" role="tablist">{maps.map((m, i) => <button key={i} role="tab" aria-selected={segment === i} className={segment === i ? 'active' : ''} onClick={() => setSegment(i)}>{labelFor(m.segment_id, i)}</button>)}</div>}
      <SeatMap key={map.segment_id ?? segment} map={map} passengers={ids} passengerLabel={passengerLabel} choices={seats}
        onChoose={(c) => setSeats((all) => [...all.filter((x) => !(x.segmentId === c.segmentId && x.passengerId === c.passengerId)), ...(c.designator ? [c as SeatChoice] : [])])} />
      <p className="muted small tab-note">Seat availability and prices come from the airline via {f.provider} and are reserved only when the booking is made with the airline. {f.data_status !== 'live' ? 'This is sandbox data.' : ''}</p>
    </>
  );
}

function InfoTile({ icon, title, lines }: { icon: ReactNode; title: string; lines: string[] }) {
  return <div className="info-tile"><span className="icon-square">{icon}</span><div><b>{title}</b>{lines.map((l, i) => <small key={i}>{l}</small>)}</div></div>;
}

/** Every airport the itinerary touches, in order, with coordinates for the map. */
function useItineraryStops(f: Flight): AirportRef[] {
  const codes = useMemo(() => {
    const out: string[] = [];
    for (const leg of legsOf(f)) {
      const seq = leg.segments.length ? [leg.segments[0].origin, ...leg.segments.map((s) => s.destination)] : [leg.origin, leg.destination];
      for (const c of seq) if (out[out.length - 1] !== c) out.push(c);
    }
    return out;
  }, [f]);
  const [stops, setStops] = useState<AirportRef[]>([]);
  useEffect(() => {
    const build = () => setStops(codes.map((c) => knownAirport(c)).filter((a): a is AirportRef => !!a && a.lat != null));
    const missing = [...new Set(codes.filter((c) => knownAirport(c)?.lat == null))];
    if (!missing.length) { build(); return; }
    api<Airport[]>(`/api/airports/lookup?codes=${missing.join(',')}`).then((r) => { rememberAirports(r.map(toRef)); build(); }).catch(() => setStops([]));
  }, [codes]);
  return stops;
}
