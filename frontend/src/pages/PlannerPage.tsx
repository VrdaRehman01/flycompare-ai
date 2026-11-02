import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { BedDouble, BookOpen, Bookmark, CalendarRange, Car, CloudRain, Coffee, Lightbulb, MapPin, Plane, Printer, Sparkles, Sun, Trash2, Users, Utensils, Wand2 } from 'lucide-react';
import type { SearchRouteFn } from '../App';
import { AirportField } from '../components/AirportField';
import { MediaPhoto } from '../components/MediaPhoto';
import { useToast } from '../state';
import { DateField } from '../components/Pickers';
import { GuestPicker, TravelHero, useTrip } from '../components/TravelUI';
import { EmptyState, Loading, Notice, Price, SegmentedControl, useDisplayCurrency } from '../components/ui';
import { api, errorText } from '../lib/api';
import { fullDate, shortDate } from '../lib/format';
import { useFeatures } from '../lib/features';
import { navigate } from '../lib/router';
import { INTERESTS, nightsBetween, type Budget, type Pace, type Plan, type PlanItem } from '../lib/travel';
import type { AirportRef } from '../lib/types';

const SAVED_KEY = 'fc-saved-plans';
type SavedPlan = { id: string; saved_at: string; plan: Plan };
const readSaved = (): SavedPlan[] => { try { return JSON.parse(localStorage.getItem(SAVED_KEY) ?? '[]') as SavedPlan[]; } catch { return []; } };
const writeSaved = (list: SavedPlan[]) => { try { localStorage.setItem(SAVED_KEY, JSON.stringify(list.slice(0, 12))); } catch { /* storage blocked */ } };

export function PlannerPage({ location, origin, onSearchRoute }: { location?: string; origin: AirportRef | null; onSearchRoute: SearchRouteFn }) {
  const [trip, setTrip] = useTrip(location);
  const [interests, setInterests] = useState<string[]>(['Culture', 'Food']);
  const [pace, setPace] = useState<Pace>('balanced');
  const [budget, setBudget] = useState<Budget>('mid');
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedPlan[]>(readSaved);
  const toast = useToast();
  const features = useFeatures();

  const make = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!trip.destination) { setError('Choose a destination.'); return; }
    const nights = nightsBetween(trip.start, trip.end);
    if (nights < 1 || nights > 21) { setError('Choose a trip of 1 to 21 nights.'); return; }
    setError(null); setBusy(true);
    const updating = !!plan;
    try {
      setPlan(await api<Plan>('/api/planner/plan', { method: 'POST', body: { location: trip.destination.code, start: trip.start, end: trip.end, travellers: trip.adults + trip.children, interests, pace, budget } }));
      if (updating) toast('success', 'Plan updated with your new choices.');
      window.setTimeout(() => document.getElementById('plan-top')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  useEffect(() => { if (location && trip.destination && !plan) void make(); }, [trip.destination?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = () => {
    if (!plan) return;
    const id = `${plan.city.key}|${plan.start}|${plan.end}`;
    const next = [{ id, saved_at: new Date().toISOString(), plan }, ...saved.filter((s) => s.id !== id)];
    setSaved(next); writeSaved(next);
  };
  const remove = (id: string) => { const next = saved.filter((s) => s.id !== id); setSaved(next); writeSaved(next); };
  const isSaved = plan && saved.some((s) => s.id === `${plan.city.key}|${plan.start}|${plan.end}`);

  return (
    <div className="container page travel-page planner-page">
      <TravelHero icon={<Wand2 size={13} />} eyebrow="TRIP PLANNER" title="Plan your trip, day by day" place={trip.destination} art={<CalendarRange size={64} />}
        subtitle="Tell us where, when and what you enjoy. We build an itinerary around real sights, the weather and your budget, then link each part to flights, stays and tours.">
        <form className="planner-form" onSubmit={make} noValidate>
          <div className="travel-form planner-row">
            <AirportField label="Destination" value={trip.destination} onChange={(a) => setTrip({ destination: a })} />
            <DateField label="Arrive" endLabel="Leave" start={trip.start} end={trip.end} range onChange={(s, e) => setTrip({ start: s, end: e })} />
            <GuestPicker adults={trip.adults} children={trip.children} showRooms={false} maxAdults={12} onChange={(g) => setTrip({ adults: g.adults, children: g.children })} />
          </div>
          <div className="planner-options">
            <div><span className="opt-label">Interests</span>
              <div className="chip-wrap">{INTERESTS.map((i) => <button type="button" key={i} className={`chip small ${interests.includes(i) ? 'active' : ''}`} aria-pressed={interests.includes(i)} onClick={() => setInterests(interests.includes(i) ? interests.filter((x) => x !== i) : [...interests, i])}>{i}</button>)}</div>
            </div>
            <div><span className="opt-label">Pace</span><SegmentedControl label="Pace" value={pace} onChange={setPace} options={[{ value: 'relaxed', label: 'Relaxed' }, { value: 'balanced', label: 'Balanced' }, { value: 'packed', label: 'Packed' }]} /></div>
            <div><span className="opt-label">Budget</span><SegmentedControl label="Budget" value={budget} onChange={setBudget} options={[{ value: 'budget', label: 'Budget' }, { value: 'mid', label: 'Mid-range' }, { value: 'luxury', label: 'Luxury' }]} /></div>
            <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Sparkles size={16} />} {plan ? 'Update plan' : 'Build my plan'}</button>
          </div>
        </form>
      </TravelHero>

      {saved.length > 0 && (
        <div className="saved-plans">
          <b><Bookmark size={14} /> Saved plans</b>
          {saved.map((s) => (
            <span key={s.id} className="saved-plan">
              <button className="chip small" onClick={() => setPlan(s.plan)}>{s.plan.city.city} · {shortDate(s.plan.start)}–{shortDate(s.plan.end)}</button>
              <button className="icon-btn small" onClick={() => remove(s.id)} aria-label={`Remove saved plan for ${s.plan.city.city}`}><Trash2 size={13} /></button>
            </span>
          ))}
        </div>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {busy && !plan && <Loading label="Building your itinerary…" />}
      {!plan && !busy && <div className="card"><EmptyState icon={<CalendarRange size={30} />} title="Your itinerary will appear here">Pick a destination and dates, choose what you enjoy, and we'll draft the days for you.</EmptyState></div>}

      {plan && (
        <div id="plan-top" className={`planner-layout ${busy ? 'is-refreshing' : ''}`}>
          <div className="planner-main">
            <div className="planner-head card">
              <div>
                <h2>{plan.nights} night{plan.nights === 1 ? '' : 's'} in {plan.city.city}</h2>
                <p className="muted">{fullDate(plan.start)} – {fullDate(plan.end)} · {plan.travellers} traveller{plan.travellers === 1 ? '' : 's'} · {plan.pace} pace · {plan.budget === 'mid' ? 'mid-range' : plan.budget}{plan.interests.length ? ` · ${plan.interests.join(', ')}` : ''}</p>
              </div>
              <div className="planner-actions no-print">
                <button className="btn btn-soft" onClick={save} disabled={!!isSaved}><Bookmark size={15} /> {isSaved ? 'Saved' : 'Save'}</button>
                <button className="btn btn-ghost" onClick={() => window.print()}><Printer size={15} /> Print</button>
              </div>
            </div>
            {plan.note && <Notice>{plan.note}</Notice>}
            <WeatherStrip plan={plan} />
            <ol className="day-list">
              {plan.days.map((d, n) => (
                <li key={d.date} className="card day-card">
                  <div className="day-head">
                    <span className="day-num">Day {n + 1}</span>
                    <div><b>{d.title}</b><small className="muted">{shortDate(d.date)} · <MapPin size={11} /> {d.area}</small></div>
                    {d.activities_usd > 0 && <small className="muted day-cost">Admissions <Price amount={d.activities_usd * plan.travellers} currency="USD" inline /></small>}
                  </div>
                  <ul className="timeline">{d.items.map((i, k) => <TimelineItem key={k} item={i} city={plan.city.city} />)}</ul>
                </li>
              ))}
            </ol>
          </div>

          <aside className="planner-side">
            <CostCard plan={plan} />
            <section className="card panel book-links no-print">
              <h3>Book the pieces</h3>
              <button className="book-link" disabled={!origin || origin.code === plan.city.airport} onClick={() => origin && onSearchRoute(origin.code, plan.city.airport, { departure: plan.start, returnDate: plan.end, tripType: 'round-trip' })}>
                <Plane size={16} /><span><b>Flights</b><small>{origin ? `${origin.code} → ${plan.city.airport}, ${shortDate(plan.start)} – ${shortDate(plan.end)}` : 'Set your departure airport on the Flights page'}</small></span>
              </button>
              {features.has('stays') && <button className="book-link" onClick={() => navigate({ page: 'stays', location: plan.city.airport })}><BedDouble size={16} /><span><b>Stays</b><small>Hotels and homes for these dates</small></span></button>}
              {features.has('packages') && <button className="book-link" onClick={() => navigate({ page: 'packages', location: plan.city.airport })}><Sparkles size={16} /><span><b>Flight & Hotel</b><small>See flight and stay together</small></span></button>}
              {features.has('tours') && <button className="book-link" onClick={() => navigate({ page: 'tours', kind: 'group', location: plan.city.airport })}><Users size={16} /><span><b>Tours</b><small>Guided versions of these sights</small></span></button>}
              {features.has('transfers') && <button className="book-link" onClick={() => navigate({ page: 'cars', tab: 'transfers', location: plan.city.airport })}><Car size={16} /><span><b>Airport transfer</b><small>{plan.city.airports[0]?.name}</small></span></button>}
              <button className="book-link" onClick={() => navigate({ page: 'guides', location: plan.city.airport })}><BookOpen size={16} /><span><b>Travel guide</b><small>Areas, sights and tips</small></span></button>
            </section>
            {plan.tips.length > 0 && (
              <section className="card panel">
                <h3><Lightbulb size={15} /> Tips for this trip</h3>
                <ul className="tip-list">{plan.tips.map((t) => <li key={t}>{t}</li>)}</ul>
              </section>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

const ITEM_ICON: Record<PlanItem['kind'], ReactNode> = { sight: <MapPin size={13} />, meal: <Utensils size={13} />, free: <Coffee size={13} />, travel: <Plane size={13} /> };

function TimelineItem({ item: i, city }: { item: PlanItem; city: string }) {
  return (
    <li className={`tl-item ${i.kind}`}>
      <span className="tl-time">{i.time}</span>
      <span className="tl-dot">{ITEM_ICON[i.kind]}</span>
      <div className={`tl-body ${i.kind === 'sight' ? 'has-thumb' : ''}`}>
        {i.kind === 'sight' && <MediaPhoto q={i.title} context={city} icon={<MapPin size={20} />} alt={i.title} className="tl-thumb" />}
        <div>
          <b>{i.title}</b>{i.category && <span className="tag">{i.category}</span>}
          <p>{i.detail}</p>
          {i.kind === 'sight' && <small className="muted">{i.hours} h · {i.usd ? <>typically <Price amount={i.usd} currency="USD" inline /> per person</> : 'free'}</small>}
        </div>
      </div>
    </li>
  );
}

function WeatherStrip({ plan }: { plan: Plan }) {
  const w = plan.weather;
  if (!w) return null;
  return (
    <section className="card weather-strip">
      <b>{w.kind === 'forecast' ? <><Sun size={15} /> Forecast</> : <><CloudRain size={15} /> Typical weather</>}</b>
      <div className="weather-days">
        {w.kind === 'forecast'
          ? w.days.map((d) => <span key={d.date}><small>{shortDate(d.date)}</small><b>{d.max_c != null ? Math.round(d.max_c) : '–'}° / {d.min_c != null ? Math.round(d.min_c) : '–'}°</b><small>{d.condition}{d.precipitation_probability != null ? ` · ${d.precipitation_probability}% rain` : ''}</small></span>)
          : w.months.map((m) => <span key={m.month}><small>{m.name}</small><b>{Math.round(m.avg_high_c)}° / {m.avg_low_c != null ? Math.round(m.avg_low_c) : '–'}°</b><small>{m.rainy_days} rainy days</small></span>)}
      </div>
      <small className="muted">{w.source}</small>
    </section>
  );
}

function CostCard({ plan }: { plan: Plan }) {
  const cur = useDisplayCurrency(plan.costs.currency);
  return (
    <section className="card panel cost-card">
      <h3>Estimated cost</h3>
      {plan.costs.lines.map((l) => <p key={l.label}><span>{l.label}</span><b>{cur.format(l.amount)}</b></p>)}
      <div className="cost-total"><span>Total, excluding flights</span><strong>{cur.format(plan.costs.total)}</strong>
        {plan.travellers > 1 && <small>{cur.format(plan.costs.total / plan.travellers)} per traveller</small>}</div>
      <small className="muted">{plan.costs.basis} {plan.costs.excludes}{cur.approx ? ` Converted from USD at reference rates.` : ''}</small>
    </section>
  );
}
