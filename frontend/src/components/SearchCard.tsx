import { useState, type FormEvent } from 'react';
import { ArrowLeftRight, ArrowRight, Armchair, LocateFixed, Plus, Route, Search, Sparkles, Trash2 } from 'lucide-react';
import { addDays } from '../lib/calendar';
import type { GeoState } from '../lib/geo';
import { CABINS, type AirportRef, type Cabin, type SearchForm, type TripType } from '../lib/types';
import { MAX_LEGS, validateSearch, type FieldErrors } from '../lib/validation';
import { AirportField, type LocationStatus } from './AirportField';
import { Listbox } from './Listbox';
import { DateField, PassengerPicker } from './Pickers';
import { Notice } from './ui';

type Props = {
  form: SearchForm;
  update: (p: Partial<SearchForm>) => void;
  onOriginChange: (a: AirportRef | null) => void;
  onSearch: (f: SearchForm) => void;
  loading: boolean;
  error: string | null;
  location: { status: LocationStatus; geoState: GeoState; locate: () => void; dismiss: () => void };
};

const TRIPS: { value: TripType; label: string; icon: JSX.Element }[] = [
  { value: 'round-trip', label: 'Round trip', icon: <ArrowLeftRight size={15} /> },
  { value: 'one-way', label: 'One way', icon: <ArrowRight size={15} /> },
  { value: 'multi-city', label: 'Multi-city', icon: <Route size={15} /> },
];

export function SearchCard({ form, update, onOriginChange, onSearch, loading, error, location }: Props) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const clear = (...keys: string[]) => setErrors((e) => { const n = { ...e }; keys.forEach((k) => delete n[k]); return n; });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const found = validateSearch(form);
    setErrors(found);
    if (!Object.keys(found).length) onSearch(form);
  };
  const setTrip = (t: TripType) => {
    if (t === form.tripType) return;
    if (t === 'multi-city') {
      // Start the itinerary from what the visitor already entered.
      const legs = [{ origin: form.origin, destination: form.destination, date: form.departure }, { origin: form.destination, destination: null, date: '' }];
      update({ tripType: t, legs: form.legs.some((l) => l.origin || l.destination) && form.tripType === 'multi-city' ? form.legs : legs });
    } else {
      update({ tripType: t, returnDate: t === 'one-way' ? '' : form.returnDate });
    }
    setErrors({});
  };
  const setLeg = (i: number, patch: Partial<SearchForm['legs'][number]>) => {
    const legs = form.legs.map((l, j) => (j === i ? { ...l, ...patch } : l));
    // The next flight usually departs from where this one lands.
    if (patch.destination && legs[i + 1] && !legs[i + 1].origin) legs[i + 1] = { ...legs[i + 1], origin: patch.destination };
    update({ legs });
  };
  const showLocationPrompt = !form.origin && location.geoState === 'unasked' && location.status.state === 'idle' && 'geolocation' in navigator;

  return (
    <form id="search-card" className="search-card" onSubmit={submit} noValidate>
      <div className="search-tabs" role="tablist" aria-label="Trip type">
        {TRIPS.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={form.tripType === t.value} className={form.tripType === t.value ? 'active' : ''} onClick={() => setTrip(t.value)}>{t.icon} {t.label}</button>
        ))}
      </div>
      <div className="search-options">
        <span className="search-hint"><Sparkles size={14} /> We compare total journey time, stops and baggage — not just price.</span>
        <div className="option-selects">
          <PassengerPicker value={form.passengers} onChange={(p) => { update({ passengers: p }); clear('passengers'); }} error={errors.passengers} />
          <Listbox label="Cabin class" icon={<Armchair size={14} />} value={form.cabin} onChange={(c) => update({ cabin: c as Cabin })} options={CABINS.map((c) => ({ value: c, label: c }))} align="right" />
        </div>
      </div>
      {errors.passengers && <Notice kind="error">{errors.passengers}</Notice>}

      {showLocationPrompt && (
        <div className="location-prompt">
          <LocateFixed size={16} />
          <span>Start from your nearest airport? We only use your location to find it and don’t store it.</span>
          <button type="button" className="btn btn-soft small" onClick={location.locate}>Use my location</button>
          <button type="button" className="link-btn small" onClick={location.dismiss}>Choose manually</button>
        </div>
      )}

      {form.tripType === 'multi-city' ? (
        <div className="multi-legs">
          {form.legs.map((leg, i) => (
            <div className="multi-leg" key={i}>
              <span className="leg-number">Flight {i + 1}</span>
              <AirportField label="From" value={leg.origin} exclude={leg.destination?.code} error={errors[`leg${i}.origin`]}
                onChange={(a) => { setLeg(i, { origin: a }); clear(`leg${i}.origin`); if (i === 0) onOriginChange(a); }} />
              <AirportField label="To" value={leg.destination} exclude={leg.origin?.code} error={errors[`leg${i}.destination`]}
                onChange={(a) => { setLeg(i, { destination: a }); clear(`leg${i}.destination`); }} />
              <DateField label="Date" start={leg.date} min={i ? form.legs[i - 1].date : undefined} error={errors[`leg${i}.date`]}
                onChange={(d) => { setLeg(i, { date: d }); clear(`leg${i}.date`); }} />
              <button type="button" className="icon-btn danger" disabled={form.legs.length <= 2} onClick={() => update({ legs: form.legs.filter((_, j) => j !== i) })} aria-label={`Remove flight ${i + 1}`}><Trash2 size={16} /></button>
            </div>
          ))}
          <div className="multi-actions">
            <button type="button" className="btn btn-soft" disabled={form.legs.length >= MAX_LEGS}
              onClick={() => { const last = form.legs[form.legs.length - 1]; update({ legs: [...form.legs, { origin: last.destination, destination: null, date: last.date ? addDays(last.date, 3) : '' }] }); }}>
              <Plus size={15} /> Add flight
            </button>
            <span className="muted small">Up to {MAX_LEGS} flights, priced together as one itinerary.</span>
            <button className="search-btn wide" disabled={loading}>{loading ? <span className="spinner" /> : <Search size={20} />} {loading ? 'Searching…' : 'Search flights'}</button>
          </div>
        </div>
      ) : (
        <div className={`search-fields ${form.tripType}`}>
          <div className="route-pair">
            <AirportField label="From" value={form.origin} exclude={form.destination?.code} error={errors.origin} onUseLocation={location.locate} locationStatus={location.status}
              onChange={(a) => { onOriginChange(a); clear('origin', 'destination'); }} />
            <button type="button" className="swap-btn" onClick={() => { const o = form.origin; onOriginChange(form.destination); update({ destination: o }); clear('origin', 'destination'); }} aria-label="Swap origin and destination" disabled={!form.origin && !form.destination}><ArrowLeftRight size={15} /></button>
            <AirportField label="To" value={form.destination} exclude={form.origin?.code} error={errors.destination} onChange={(a) => { update({ destination: a }); clear('destination'); }} />
          </div>
          <DateField label="Departure" start={form.departure} end={form.returnDate} range={form.tripType === 'round-trip'} error={errors.departure ?? errors.returnDate}
            fares={form.origin && form.destination ? { origin: form.origin.code, destination: form.destination.code, tripType: form.tripType, cabin: form.cabin, passengers: form.passengers } : null}
            onChange={(s, e) => { update({ departure: s, returnDate: form.tripType === 'round-trip' ? e : '' }); clear('departure', 'returnDate'); }} />
          <button className="search-btn" disabled={loading} aria-label="Search flights">
            {loading ? <span className="spinner" /> : <Search size={22} />}<span className="search-btn-text">{loading ? 'Searching…' : 'Search'}</span>
          </button>
        </div>
      )}
      {loading && <p className="search-progress">Searching the provider for available offers. This can take up to 30 seconds…</p>}
      {error && <Notice kind="error">{error}</Notice>}
    </form>
  );
}
