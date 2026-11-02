import { useEffect, useState, type FormEvent } from 'react';
import { BookOpen, CalendarDays, Car, ChevronDown, Clock3, Flag, Languages, MapPin, Search, ShieldCheck, Star, Ticket, UserRound, Users } from 'lucide-react';
import { AirportField } from '../components/AirportField';
import { Listbox } from '../components/Listbox';
import { MediaPhoto } from '../components/MediaPhoto';
import { DateField } from '../components/Pickers';
import { GuestPicker, ProviderNotice, TravelHero, useTrip } from '../components/TravelUI';
import { EmptyState, Loading, Notice, Price } from '../components/ui';
import { api, errorText } from '../lib/api';
import { navigate, type TourKind } from '../lib/router';
import type { GuideCard, Tour, ToursResponse } from '../lib/travel';

export function ToursPage({ kind, location }: { kind: TourKind; location?: string }) {
  const [trip, setTrip] = useTrip(location);
  const [date, setDate] = useState(trip.start);
  const [data, setData] = useState<ToursResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState('All');
  const [sort, setSort] = useState<'rating' | 'price' | 'duration'>('rating');
  const [open, setOpen] = useState<string | null>(null);
  const [guides, setGuides] = useState<GuideCard[]>([]);
  const travellers = trip.adults + trip.children;

  useEffect(() => { api<{ items: GuideCard[] }>('/api/guides').then((g) => setGuides(g.items)).catch(() => setGuides([])); }, []);

  const search = (e?: FormEvent) => {
    e?.preventDefault();
    if (!trip.destination) { setError('Choose a city.'); return; }
    setError(null); setBusy(true);
    const q = new URLSearchParams({ location: trip.destination.code, date, travellers: String(travellers), kind });
    api<ToursResponse>(`/api/tours/search?${q}`).then((d) => { setData(d); setCategory('All'); }).catch((err) => setError(errorText(err))).finally(() => setBusy(false));
  };
  useEffect(() => { if (trip.destination) search(); }, [trip.destination?.code, kind]); // eslint-disable-line react-hooks/exhaustive-deps

  const results = data?.results ?? [];
  const categories = ['All', ...new Set(results.flatMap((t) => t.categories))];
  const shown = results.filter((t) => category === 'All' || t.categories.includes(category))
    .sort((a, b) => sort === 'price' ? a.total_price - b.total_price : sort === 'duration' ? a.duration_hours - b.duration_hours : b.rating - a.rating);
  const isGroup = kind === 'group';

  return (
    <div className="container page travel-page">
      <TravelHero icon={isGroup ? <Users size={13} /> : <UserRound size={13} />} eyebrow={isGroup ? 'GROUP TOURS' : 'PRIVATE TOURS'}
        title={isGroup ? 'Join a small-group tour' : 'Book a private tour'} place={trip.destination} art={isGroup ? <Users size={64} /> : <UserRound size={64} />}
        subtitle={isGroup ? 'Shared guided tours with fixed start times, priced per person. A sociable, budget-friendly way to see the sights.' : 'Your own guide and vehicle with hotel pickup and a flexible start, priced per party. Better value the more of you there are.'}
        tabs={(
          <div className="segmented travel-tablist" role="tablist">
            <button role="tab" aria-selected={isGroup} className={isGroup ? 'active' : ''} onClick={() => navigate({ page: 'tours', kind: 'group', location })}><Users size={15} /> Group tours</button>
            <button role="tab" aria-selected={!isGroup} className={!isGroup ? 'active' : ''} onClick={() => navigate({ page: 'tours', kind: 'private', location })}><UserRound size={15} /> Private tours</button>
          </div>
        )}>
        <form className="travel-form tours-form" onSubmit={search} noValidate>
          <AirportField label="City" value={trip.destination} onChange={(a) => setTrip({ destination: a })} />
          <DateField label="Tour date" start={date} onChange={(s) => setDate(s)} />
          <GuestPicker adults={trip.adults} children={trip.children} showRooms={false} maxAdults={20} onChange={(g) => setTrip({ adults: g.adults, children: g.children })} />
          <button className="btn btn-primary travel-go" disabled={busy}>{busy ? <span className="spinner" /> : <Search size={16} />} Find tours</button>
        </form>
      </TravelHero>

      {error && <Notice kind="error">{error}</Notice>}
      {busy && !data && <Loading label="Finding tours…" />}
      {!busy && !guides.length && (!data || !results.length) && (
        <div className="card"><EmptyState icon={<Users size={30} />} title={data ? 'No tours found' : 'Where would you like to explore?'}>{data?.notice ?? 'Choose a city and date to see guided tours.'}</EmptyState></div>
      )}
      {(!data || !results.length) && !busy && guides.length > 0 && (
        <div className="card guide-chips">
          {data && <ProviderNotice status={data.data_status} notice={data.notice} />}
          <b>{data ? 'Try one of these cities' : 'Popular tour cities'}</b>
          <div className="chip-wrap">{guides.map((g) => <button key={g.key} className="chip" onClick={() => navigate({ page: 'tours', kind, location: g.airport })}><MapPin size={12} /> {g.city}</button>)}</div>
        </div>
      )}

      {data && results.length > 0 && (
        <div className={busy ? 'is-refreshing' : ''}>
          <ProviderNotice status={data.data_status} notice={data.notice} />
          <div className="results-bar">
            <div className="chip-wrap">{categories.map((c) => <button key={c} className={`chip small ${category === c ? 'active' : ''}`} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}</div>
            <Listbox label="Sort" value={sort} onChange={(v) => setSort(v as typeof sort)} align="right" options={[{ value: 'rating', label: 'Top rated' }, { value: 'price', label: 'Lowest price' }, { value: 'duration', label: 'Shortest' }]} />
          </div>
          <p className="results-caption">{shown.length} {isGroup ? 'group' : 'private'} tour{shown.length === 1 ? '' : 's'} in {data.city.city} for {travellers} traveller{travellers === 1 ? '' : 's'} ·{' '}
            <button className="link-btn small" onClick={() => navigate({ page: 'guides', location: data.city.airport })}><BookOpen size={12} /> {data.city.city} travel guide</button></p>
          <div className="tile-grid">
            {shown.map((t) => <TourCard key={t.id} tour={t} city={data.city.city} travellers={travellers} open={open === t.id} onToggle={() => setOpen(open === t.id ? null : t.id)} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function TourCard({ tour: t, city, travellers, open, onToggle }: { tour: Tour; city: string; travellers: number; open: boolean; onToggle: () => void }) {
  const lead = t.stops[0];
  return (
    <article className={`card tile ${open ? 'is-open' : ''}`}>
      <MediaPhoto q={lead.name} context={city} icon={t.kind === 'group' ? <Users size={46} /> : <UserRound size={46} />} alt={lead.name} className="tile-photo"
        label={<><span className="tag solid">{t.categories[0]}</span>{t.spots_left ? <span className="badge amber">{t.spots_left} spots left</span> : null}</>} />
      <div className="tile-body">
        <span className="tile-rating"><Star size={12} /> {t.rating.toFixed(1)} <small>({t.reviews.toLocaleString()})</small></span>
        <h3>{t.title}</h3>
        <ul className="spec-list">
          <li><Clock3 size={13} /> {t.duration_hours} h</li>
          <li><Flag size={13} /> {t.stops.length} stop{t.stops.length === 1 ? '' : 's'}</li>
          {t.group_size_max ? <li><Users size={13} /> Max {t.group_size_max}</li> : <li><Car size={13} /> {t.vehicle}</li>}
        </ul>
        <p className="tile-note"><span className="good-text"><ShieldCheck size={13} /> Free cancellation</span>{t.admission_included_usd > 0 ? <> · <Ticket size={12} /> Tickets included</> : null}</p>
        {open && (
          <div className="tile-details">
            <p>{t.summary}</p>
            <ol className="tour-stops">{t.stops.map((s) => <li key={s.name}><b>{s.name}</b> <small>{s.hours} h</small><p>{s.blurb}</p></li>)}</ol>
            <ul>
              <li><CalendarDays size={13} /> Starts {t.start_times.join(' or ')}</li>
              <li><MapPin size={13} /> {t.pickup}</li>
              <li><Languages size={13} /> {t.languages.join(', ')}</li>
              <li><Ticket size={13} /> Includes {t.includes.join(', ').toLowerCase()}</li>
            </ul>
            {t.customisable && <p className="muted">Private tours can be adjusted with your guide: swap stops or change the pace.</p>}
          </div>
        )}
        <div className="tile-foot">
          <span className="tile-price"><small>{travellers} traveller{travellers === 1 ? '' : 's'} · <Price amount={t.price_per_person} currency={t.currency} inline /> each</small><Price amount={t.total_price} currency={t.currency} /></span>
          <button className="link-btn small" onClick={onToggle} aria-expanded={open}>{open ? 'Less' : 'Itinerary'} <ChevronDown size={12} className={open ? 'flip' : ''} /></button>
        </div>
      </div>
    </article>
  );
}
