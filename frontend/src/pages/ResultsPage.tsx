import { useEffect, useMemo, useState, type CSSProperties, type FormEvent, type ReactNode } from 'react';
import { ArrowRight, BellRing, Check, ChevronDown, Filter, Info, LineChart as LineIcon, Map as MapIcon, Plane, Search, SlidersHorizontal, Sparkles, X } from 'lucide-react';
import { FlightCard } from '../components/FlightCard';
import { Modal, Notice, Price, StatusPill } from '../components/ui';
import { PriceTrendChart } from '../components/charts';
import { LazyWorldMap } from '../components/LazyMap';
import { api, errorText } from '../lib/api';
import { dateTime, dayMonth, durationLabel, knownAirport, legsOf, money, rememberAirports, toRef } from '../lib/format';
import { passengerSummary, travellerCount } from '../lib/validation';
import { activeFilterCount, applyFilters, emptyFilters, facets, SCORE_WEIGHTS, scoreResults, sortResults, TIME_WINDOWS, totalDurationOf, type Filters, type Sort, type StopKey } from '../lib/results';
import { AirlineLogo } from '../illustrations';
import type { Airport, AirportRef, FareEstimate, Flight, NearbyDate, PriceHistory, SearchForm, SearchState } from '../lib/types';
import { useAuth, useToast } from '../state';

const PAGE_SIZE = 20;

/** "Email me when this trip gets cheaper": creates or updates a price alert for the searched dates. */
function PriceAlertButton({ from, to, departure, returnDate, lowest, currency }: {
  from: string; to: string; departure: string; returnDate: string | null; lowest: number | null; currency: string;
}) {
  const { user, openAuth } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(() => (lowest ? String(Math.floor(lowest * 0.9)) : ''));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const start = () => {
    if (!user) { openAuth('login', 'Sign in to get price alerts by email.', () => setOpen(true)); return; }
    setOpen(true);
  };
  const save = async (e: FormEvent) => {
    e.preventDefault();
    const value = Number(target);
    if (!(value > 0)) { setError('Enter a target price above zero.'); return; }
    setBusy(true); setError('');
    try {
      await api('/api/account/alerts', { method: 'POST', body: { origin: from, destination: to, departure_date: departure, return_date: returnDate, target_price: value, currency } });
      setOpen(false);
      toast('success', `Alert set: we'll email you when ${from} → ${to} drops to ${money(value, currency)} or less.`);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return (
    <>
      <button className="btn btn-ghost" onClick={start}><BellRing size={15} /> Price alert</button>
      {open && (
        <Modal title="Get a price alert" onClose={() => setOpen(false)}>
          <form className="form" onSubmit={save} noValidate>
            <p className="muted small">We'll check {from} → {to}, {dayMonth(departure)}{returnDate ? ` – ${dayMonth(returnDate)}` : ' (one way)'}, every few hours and email {user?.email} when the lowest fare for one adult in economy reaches your target.</p>
            <label className="form-field"><span>Email me when it costs at most ({currency})</span>
              <input type="number" inputMode="decimal" min={1} step="1" value={target} onChange={(e) => setTarget(e.target.value)} autoFocus />
              {lowest != null && <small>Lowest fare right now: {money(lowest, currency)}</small>}
            </label>
            {error && <Notice kind="error">{error}</Notice>}
            <button className="btn btn-primary full" disabled={busy}>{busy && <span className="spinner" />}Create alert</button>
            <p className="modal-fine">Manage alerts any time under Account → Price alerts.</p>
          </form>
        </Modal>
      )}
    </>
  );
}

/** Shown instead of a bare "no flights" when the source has real fares on nearby dates. */
function NearbyDates({ dates, onPick, onEdit }: { dates: NearbyDate[]; onPick: (patch: Partial<SearchForm>) => void; onEdit: () => void }) {
  return (
    <div className="card empty-state">
      <Plane size={32} />
      <h3>No fares for these exact dates</h3>
      <p>The fare source only holds prices travellers found recently. These nearby dates on the same route have real fares:</p>
      <div className="nearby-dates">
        {dates.map((d) => (
          <button key={`${d.departure_date}-${d.return_date}`} className="nearby-date" onClick={() => onPick({ departure: d.departure_date, ...(d.return_date ? { returnDate: d.return_date } : {}) })}>
            <span>{dayMonth(d.departure_date)}{d.return_date ? ` – ${dayMonth(d.return_date)}` : ''}</span>
            <small>from</small>
            <Price amount={d.price} currency={d.currency} inline />
          </button>
        ))}
      </div>
      <p className="small">Prices are for one adult in economy; check the final price on the booking site.</p>
      <button className="btn btn-soft" onClick={onEdit}>Modify search</button>
    </div>
  );
}

export function ResultsPage({ search, onEdit, onSelect, onSearchAgain }: {
  search: SearchState; onEdit: () => void; onSelect: (f: Flight) => void; onSearchAgain: (patch: Partial<SearchForm>) => void;
}) {
  const { query, response } = search;
  const results = response.results;
  const { isSaved, toggleSaved } = useAuth();
  const [sort, setSort] = useState<Sort>('recommended');
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [showAllAirlines, setShowAllAirlines] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [shown, setShown] = useState(PAGE_SIZE);
  const [showRankInfo, setShowRankInfo] = useState(false);

  const facet = useMemo(() => facets(results), [results]);
  const filtered = useMemo(() => applyFilters(results, filters), [results, filters]);
  const scores = useMemo(() => scoreResults(filtered), [filtered]);
  const ranked = useMemo(() => ({
    recommended: sortResults(filtered, 'recommended', scores), cheapest: sortResults(filtered, 'cheapest', scores), fastest: sortResults(filtered, 'fastest', scores),
  }), [filtered, scores]);
  const list = ranked[sort];
  const cheapestId = ranked.cheapest[0]?.id, fastestId = ranked.fastest[0]?.id;
  const set = (patch: Partial<Filters>) => { setFilters((f) => ({ ...f, ...patch })); setShown(PAGE_SIZE); };
  const toggle = <T,>(arr: T[], v: T) => arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
  const reset = () => { setFilters(emptyFilters); setShown(PAGE_SIZE); };
  const multi = query.tripType === 'multi-city';
  const from = multi ? query.legs[0].origin!.code : query.origin!.code;
  const to = multi ? query.legs[query.legs.length - 1].destination!.code : query.destination!.code;
  const top = list[0];
  const routeStops = useRouteStops(top);
  const currency = facet.currencies.length === 1 ? facet.currencies[0] : null;
  const nActive = activeFilterCount(filters);
  const directOnly = filters.stops.length === 1 && filters.stops[0] === 'direct';

  return (
    <div className="container page">
      <div className="card summary-bar">
        <span className="summary-icon"><Search size={16} /></span>
        {multi ? (
          <b className="summary-route">{query.legs.map((l, i) => <span key={i}>{i ? <ArrowRight size={13} /> : null}{l.origin?.code}</span>)}<ArrowRight size={13} />{to}</b>
        ) : (
          <b className="summary-route" title={`${query.origin!.name} → ${query.destination!.name}`}>{query.origin!.city} ({from}) <ArrowRight size={14} /> {query.destination!.city} ({to})</b>
        )}
        <span className="summary-sep" />
        <span>{multi ? `${query.legs.length} flights · ${dayMonth(query.legs[0].date)} – ${dayMonth(query.legs[query.legs.length - 1].date)}` : `${dayMonth(query.departure)}${query.tripType === 'round-trip' ? ` – ${dayMonth(query.returnDate)}` : ' · One way'}`}</span>
        <span className="summary-sep" />
        <span>{passengerSummary(query.passengers)} · {query.cabin}</span>
        <StatusPill status={response.data_status} />
        {!multi && <PriceAlertButton from={from} to={to} departure={query.departure} returnDate={query.tripType === 'round-trip' ? query.returnDate : null}
          lowest={ranked.cheapest[0]?.price ?? null} currency={currency ?? 'USD'} />}
        <button className="btn btn-soft" onClick={onEdit}>Modify search</button>
      </div>
      <Notice kind={response.data_status === 'live' || response.data_status === 'recent' ? 'info' : 'warn'}>{response.source_message} <span className="muted">Searched {dateTime(search.searchedAt)}.</span></Notice>

      <div className="results-layout">
        <aside className={`card filters ${filtersOpen ? 'open' : ''}`} aria-label="Filters">
          <div className="filters-head"><b>Filters{nActive ? ` (${nActive})` : ''}</b><button className="link-btn" onClick={reset} disabled={!nActive}>Clear all</button></div>
          <FilterBlock title="Stops">
            {([['direct', 'Direct'], ['one', '1 stop'], ['two', '2+ stops']] as [StopKey, string][]).map(([k, l]) => (
              <CheckRow key={k} label={l} count={facet.stops[k]} checked={filters.stops.includes(k)} disabled={!facet.stops[k] && !filters.stops.includes(k)} onChange={() => set({ stops: toggle(filters.stops, k) })} />
            ))}
            <small className="muted">For round trips, counts the journey with the most stops.</small>
          </FilterBlock>
          {results.length > 0 && currency && (
            <FilterBlock title={`Maximum price (${currency})`}>
              <input className="range" type="range" min={facet.priceMin} max={facet.priceMax} step={1} value={filters.maxPrice ?? facet.priceMax} aria-label="Maximum price"
                onChange={(e) => { const v = Number(e.target.value); set({ maxPrice: v >= facet.priceMax ? null : v }); }} style={fill(filters.maxPrice ?? facet.priceMax, facet.priceMin, facet.priceMax)} disabled={facet.priceMin === facet.priceMax} />
              <div className="range-labels"><span>{money(facet.priceMin, currency)}</span><span>{money(filters.maxPrice ?? facet.priceMax, currency)}</span></div>
            </FilterBlock>
          )}
          {results.length > 0 && (
            <FilterBlock title="Maximum total journey time">
              <input className="range" type="range" min={0} max={facet.durationMax} step={30} value={filters.maxDuration ?? facet.durationMax} aria-label="Maximum journey time"
                onChange={(e) => { const v = Number(e.target.value); set({ maxDuration: v >= facet.durationMax ? null : v }); }} style={fill(filters.maxDuration ?? facet.durationMax, 0, facet.durationMax)} />
              <div className="range-labels"><span>Any</span><span>≤ {durationLabel(filters.maxDuration ?? facet.durationMax)}</span></div>
            </FilterBlock>
          )}
          {results.length > 0 && (['departs', 'arrives'] as const).map((key) => (
            <FilterBlock key={key} title={key === 'departs' ? 'Outbound departure time' : 'Outbound arrival time'}>
              <div className="time-windows">
                {TIME_WINDOWS.map(([w, label, range]) => {
                  const on = filters[key].includes(w);
                  const n = facet[key][w];
                  return (
                    <button key={w} className={`time-window ${on ? 'on' : ''}`} aria-pressed={on} disabled={!n && !on} onClick={() => set({ [key]: toggle(filters[key], w) } as Partial<Filters>)}>
                      <b>{label}</b><small>{range}</small><small className="muted">{n}</small>
                    </button>
                  );
                })}
              </div>
              <small className="muted">Local time at the airport.</small>
            </FilterBlock>
          ))}
          <FilterBlock title="Airlines">
            {facet.airlines.length ? (showAllAirlines ? facet.airlines : facet.airlines.slice(0, 6)).map(([a, n]) => (
              <CheckRow key={a} label={a} count={n} icon={<AirlineLogo name={a} size={20} src={facet.logos.get(a)} />} checked={filters.airlines.includes(a)} onChange={() => set({ airlines: toggle(filters.airlines, a) })} />
            )) : <small className="muted">No airlines in these results.</small>}
            {facet.airlines.length > 6 && <button className="link-btn small" onClick={() => setShowAllAirlines((v) => !v)}>{showAllAirlines ? 'Show less' : `Show all ${facet.airlines.length}`} <ChevronDown size={13} className={showAllAirlines ? 'flip' : ''} /></button>}
          </FilterBlock>
          <FilterBlock title="Baggage">
            <CheckRow label="Carry-on included" count={facet.carryOnCount} checked={filters.carryOn} disabled={!facet.carryOnCount && !filters.carryOn} onChange={() => set({ carryOn: !filters.carryOn })} />
            <CheckRow label="Checked bag included" count={facet.checkedCount} checked={filters.checked} disabled={!facet.checkedCount && !filters.checked} onChange={() => set({ checked: !filters.checked })} />
          </FilterBlock>
          <FilterBlock title="Flexibility">
            {facet.refundableKnown
              ? <CheckRow label="Refundable only" count={facet.refundableCount} checked={filters.refundableOnly} disabled={!facet.refundableCount && !filters.refundableOnly} onChange={() => set({ refundableOnly: !filters.refundableOnly })} />
              : <small className="muted">The provider did not supply refund conditions for these offers.</small>}
          </FilterBlock>
        </aside>

        <section className="results-main" aria-label="Flight results">
          <div className="results-toolbar">
            <button className="btn btn-soft filters-toggle" onClick={() => setFiltersOpen((v) => !v)} aria-expanded={filtersOpen}><SlidersHorizontal size={15} /> {filtersOpen ? 'Hide filters' : `Filters${nActive ? ` (${nActive})` : ''}`}</button>
          </div>
          <div className="sort-tabs" role="tablist" aria-label="Sort results">
            {([['recommended', 'Recommended', 'Best balance'], ['cheapest', 'Cheapest', 'Lowest price'], ['fastest', 'Fastest', 'Shortest journey']] as [Sort, string, string][]).map(([k, t, s]) => {
              const top = ranked[k][0];
              return (
                <button key={k} role="tab" aria-selected={sort === k} className={`sort-tab ${sort === k ? 'active' : ''}`} onClick={() => { setSort(k); setShown(PAGE_SIZE); }}>
                  <b>{t}</b>
                  <span>{top ? <>From <Price amount={top.price} currency={top.currency} inline /></> : '—'}</span>
                  <small>{k === 'fastest' && top ? durationLabel(totalDurationOf(top)) : s}</small>
                </button>
              );
            })}
          </div>
          <div className="results-count">
            <span><b>{list.length}</b> of {results.length} offers{nActive ? ' match your filters' : ''}</span>
            <span className="results-count-actions">
              <button className={`chip small ${directOnly ? 'active' : ''}`} onClick={() => set({ stops: directOnly ? [] : ['direct'] })} disabled={!facet.stops.direct && !directOnly}>Direct only</button>
              {sort === 'recommended' && <button className="link-btn small" onClick={() => setShowRankInfo((v) => !v)} aria-expanded={showRankInfo}><Info size={13} /> How we rank</button>}
            </span>
          </div>
          {showRankInfo && sort === 'recommended' && (
            <div className="card rank-info">
              <b>Recommended ranking</b>
              <p>Each offer gets a score from its price ({SCORE_WEIGHTS.price * 100}%), total journey time including connections ({SCORE_WEIGHTS.duration * 100}%), number of stops ({SCORE_WEIGHTS.stops * 100}%), whether a checked bag is included ({SCORE_WEIGHTS.bags * 100}%) and whether the fare is refundable ({SCORE_WEIGHTS.flex * 100}%). Price, time and stops are compared only with the other offers shown here (best 0, worst 100). Baggage and refunds score 0 when included, 100 when the provider says not, and 50 when the provider did not say. Lower totals rank higher. Open any card's itinerary to see its breakdown. No airline pays for placement.</p>
            </div>
          )}
          {results.length === 0 ? (
            response.nearby_dates?.length ? <NearbyDates dates={response.nearby_dates} onPick={onSearchAgain} onEdit={onEdit} /> :
            response.data_status === 'recent' ? (
              <div className="card empty-state">
                <Plane size={32} /><h3>No recent fares for this trip</h3>
                <p>The fare source only has prices that travellers found recently, mostly for the next few weeks and busier routes.{query.tripType === 'round-trip' ? ` It has none for ${from} → ${to} and back on or near these dates.` : ` It has none for ${from} → ${to} on or near this date.`}</p>
                <div className="empty-actions">
                  {query.tripType === 'round-trip' && <button className="btn btn-primary" onClick={() => onSearchAgain({ tripType: 'one-way', returnDate: '' })}>Search one way instead</button>}
                  <button className="btn btn-soft" onClick={onEdit}>Change dates or airports</button>
                </div>
              </div>
            ) :
            <div className="card empty-state"><Plane size={32} /><h3>No flights found</h3><p>The provider returned no offers for this route and date. Try other dates, a nearby airport, or a different cabin.</p><button className="btn btn-primary" onClick={onEdit}>Modify search</button></div>
          ) : list.length === 0 ? (
            <div className="card empty-state"><Filter size={30} /><h3>No flights match these filters</h3><p>Try widening the price or journey-time limits.</p><button className="btn btn-soft" onClick={reset}><X size={14} /> Clear all filters</button></div>
          ) : (
            <div className="flight-list">
              {list.slice(0, shown).map((f) => (
                <FlightCard key={f.id} f={f} passengers={travellerCount(query.passengers)} score={sort === 'recommended' ? scores.get(f.id) : undefined}
                  badge={f.id === cheapestId ? 'Cheapest' : f.id === fastestId ? 'Fastest' : undefined}
                  saved={isSaved(f.id)} onSave={() => void toggleSaved(f, query)} onSelect={() => onSelect(f)} />
              ))}
              {list.length > shown && <button className="btn btn-soft show-more" onClick={() => setShown((n) => n + PAGE_SIZE)}>Show {Math.min(PAGE_SIZE, list.length - shown)} more of {list.length - shown} remaining</button>}
            </div>
          )}
        </section>

        <aside className="rail">
          <div className="card map-card">
            <div className="map-badge"><MapIcon size={14} /> {top ? 'Top result route' : 'Route'}</div>
            <LazyWorldMap route={routeStops.length > 1 ? { stops: routeStops } : null} showAirports={false} height={300} caption="Map of the top result's outbound route" />
            {routeStops.length > 2 && <p className="map-note muted small">Connecting via {routeStops.slice(1, -1).map((s) => `${s.city} (${s.code})`).join(', ')} — from the top result's actual itinerary.</p>}
          </div>
          <SearchSnapshot results={results} />
          {!multi && <ObservedHistory search={search} />}
          {!multi && <ModelEstimate origin={from} destination={to} departure={query.departure} />}
        </aside>
      </div>
    </div>
  );
}

const fill = (v: number, lo: number, hi: number) => ({ '--fill': `${hi === lo ? 100 : ((v - lo) / (hi - lo)) * 100}%` }) as CSSProperties;

function FilterBlock({ title, children }: { title: string; children: ReactNode }) {
  return <fieldset className="filter-block"><legend>{title}</legend>{children}</fieldset>;
}

export function CheckRow({ label, count, checked, disabled, onChange, icon }: { label: string; count?: number; checked: boolean; disabled?: boolean; onChange: () => void; icon?: ReactNode }) {
  return (
    <label className={`check-row ${disabled ? 'disabled' : ''}`}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
      <span className="check-box"><Check size={11} strokeWidth={3} /></span>
      {icon}<span className="check-label">{label}</span>
      {count != null && <span className="check-count">{count}</span>}
    </label>
  );
}

function SearchSnapshot({ results }: { results: Flight[] }) {
  const currencies = [...new Set(results.map((r) => r.currency))];
  if (!results.length) return null;
  if (currencies.length > 1) return <div className="card insight-card"><h4>This search</h4><p className="muted small">Offers were returned in {currencies.join(', ')}; fares are not summarised across currencies.</p></div>;
  const prices = results.map((r) => r.price).sort((a, b) => a - b);
  const low = prices[0], median = prices[Math.floor(prices.length / 2)], high = prices[prices.length - 1];
  const currency = currencies[0];
  return (
    <div className="card insight-card">
      <h4>This search</h4>
      <small className="muted">Lowest of {results.length} offers</small>
      <div className="insight-price"><Price amount={low} currency={currency} /></div>
      <div className="mini-stats"><span>Median <b>{money(median, currency)}</b></span><span>Highest <b>{money(high, currency)}</b></span></div>
      <p className="muted small">A single search is a snapshot, not a trend.</p>
    </div>
  );
}

function ObservedHistory({ search }: { search: SearchState }) {
  const { query } = search;
  const [data, setData] = useState<PriceHistory | null>(null);
  const [failed, setFailed] = useState(false);
  const origin = query.origin?.code, destination = query.destination?.code;
  const comparable = query.passengers.childAges.length === 0 && query.passengers.infants === 0;
  useEffect(() => {
    if (!origin || !destination || !comparable) return;
    const params = new URLSearchParams({ origin, destination, departure_date: query.departure, cabin: query.cabin, trip_type: query.tripType, passengers: String(query.passengers.adults) });
    if (query.tripType === 'round-trip' && query.returnDate) params.set('return_date', query.returnDate);
    api<PriceHistory>(`/api/prices/history?${params}`).then(setData).catch(() => setFailed(true));
  }, [origin, destination, query]);
  if (failed) return null;
  if (!comparable) return <div className="card insight-card"><h4><LineIcon size={15} /> Observed price history</h4><p className="muted small">Price history is tracked for adult-only searches, because child and infant fares are priced differently.</p></div>;
  const group = data?.groups[0];
  return (
    <div className="card insight-card">
      <h4><LineIcon size={15} /> Observed price history</h4>
      {!data ? <small className="muted">Loading observations…</small> : !group ? (
        <p className="muted small">No provider observations stored for these exact dates yet. Simulated demo results are never recorded as history.</p>
      ) : group.sufficient_for_trend ? (
        <>
          <PriceTrendChart points={group.points} currency={group.currency} height={120} />
          {group.lowest_change && <span className={`badge ${group.lowest_change.absolute <= 0 ? 'green' : 'red'} soft`}>Lowest fare {group.lowest_change.absolute <= 0 ? 'down' : 'up'} {money(Math.abs(group.lowest_change.absolute), group.currency)} since first observation</span>}
          <p className="muted small">{group.points.length} searches over {group.distinct_days} days · <StatusPill status={group.data_status} /></p>
        </>
      ) : (
        <p className="muted small">{group.points.length} observation{group.points.length === 1 ? '' : 's'} on {group.distinct_days} day{group.distinct_days === 1 ? '' : 's'} so far. A trend is shown after at least {data.requirements.min_points} searches on {data.requirements.min_distinct_days} or more different days.</p>
      )}
    </div>
  );
}

function ModelEstimate({ origin, destination, departure }: { origin: string; destination: string; departure: string }) {
  const [est, setEst] = useState<FareEstimate | null>(null);
  useEffect(() => {
    api<FareEstimate>(`/api/prices/estimate?origin=${origin}&destination=${destination}&departure_date=${departure}`).then(setEst).catch(() => setEst(null));
  }, [origin, destination, departure]);
  if (!est) return null;
  return (
    <div className="card insight-card estimate-card">
      <h4><Sparkles size={15} /> Model estimate</h4>
      {est.available && est.estimate != null ? (
        <>
          <span className="badge soft">Prediction · not a live fare</span>
          <div className="insight-price"><Price amount={est.estimate} currency={est.currency ?? 'EUR'} /></div>
          <p className="muted small">Historical monthly median for a one-way {est.origin_city} → {est.destination_city} fare in {est.month}, from the {est.model_name} model{est.holdout_mae ? ` (typical error ± ${money(est.holdout_mae, est.currency ?? 'EUR')} on held-out data)` : ''}. It does not account for your cabin, passengers, return flight or current availability.</p>
        </>
      ) : <p className="muted small">{est.reason ?? 'No estimate available for this route.'}</p>}
    </div>
  );
}

/** Airports of the given offer's outbound journey (origin, connections, destination) with coordinates. */
function useRouteStops(offer: Flight | undefined): AirportRef[] {
  const codes = useMemo(() => {
    if (!offer) return [];
    const leg = legsOf(offer)[0];
    return leg.segments.length ? [leg.segments[0].origin, ...leg.segments.map((s) => s.destination)] : [leg.origin, leg.destination];
  }, [offer]);
  const [stops, setStops] = useState<AirportRef[]>([]);
  useEffect(() => {
    if (!codes.length) { setStops([]); return; }
    const missing = codes.filter((c) => knownAirport(c)?.lat == null);
    const build = () => setStops(codes.map((c) => knownAirport(c)).filter((a): a is AirportRef => !!a && a.lat != null));
    if (!missing.length) { build(); return; }
    api<Airport[]>(`/api/airports/lookup?codes=${[...new Set(missing)].join(',')}`).then((r) => { rememberAirports(r.map(toRef)); build(); }).catch(() => setStops([]));
  }, [codes]);
  return stops;
}
