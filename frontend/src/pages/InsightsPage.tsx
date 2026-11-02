import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowRight, BarChart3, CalendarDays, ChevronDown, Globe2, History, Info, LineChart as LineIcon, LogIn, MapPin, Plane, RefreshCw, Route, Search, Users, Wallet } from 'lucide-react';
import type { SearchRouteFn } from '../App';
import { ActivityChart, AirlineOffersChart, DailyPriceChart, DepartureFareChart, DepartureMonthsChart, PriceTrendChart } from '../components/charts';
import { Listbox } from '../components/Listbox';
import { EmptyState, Loading, Notice, Price, SegmentedControl, StatusPill, useDisplayCurrency } from '../components/ui';
import { api, errorText } from '../lib/api';
import { dayMonth, money, todayIso } from '../lib/format';
import type { Analytics, AnalyticsRange, HistoryItem, PriceHistory, RouteDailyHistory } from '../lib/types';
import { useAuth } from '../state';

const RANGES: { value: AnalyticsRange; label: string }[] = [
  { value: '7d', label: 'Last 7 days' }, { value: '30d', label: 'Last 30 days' }, { value: '90d', label: 'Last 90 days' }, { value: 'all', label: 'All time' },
];
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function InsightsPage({ historyVersion, onSearchRoute }: { historyVersion: number; onSearchRoute: SearchRouteFn }) {
  const { user, ready, openAuth } = useAuth();
  const [range, setRange] = useState<AnalyticsRange>('30d');
  const [scope, setScope] = useState<'me' | 'all'>('me');
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const effectiveScope = user ? scope : 'all';

  useEffect(() => {
    if (!ready) return;
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    api<Analytics>(`/api/insights/analytics?range=${range}&scope=${effectiveScope}`, { signal: ctrl.signal })
      .then(setData)
      .catch((err) => { if ((err as Error).name !== 'AbortError') setError(errorText(err)); })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [range, effectiveScope, ready, historyVersion, reload]);

  const rangeLabel = RANGES.find((r) => r.value === range)!.label.toLowerCase();
  const activity = useMemo(() => (data?.activity.points ?? []).map((p) => {
    const d = new Date(`${p.start}T12:00:00`);
    const g = data!.activity.granularity;
    const label = g === 'month' ? d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' }) : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    return { label, tipLabel: g === 'week' ? `Week of ${label}` : g === 'month' ? d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) : d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }), count: p.count };
  }), [data]);

  const t = data?.totals;
  const mix = data ? Object.entries(data.data_status_mix).filter(([, n]) => n > 0) : [];

  return (
    <div className="container page insights-page">
      <div className="page-head insights-hero">
        <div className="insights-hero-copy">
          <span className="insights-eyebrow"><span className="insights-eyebrow-dot" /> FLIGHT INTELLIGENCE</span>
          <h1>Travel Insights</h1>
          <p>{effectiveScope === 'me' ? 'Your search activity, calculated from the searches saved to your account.' : 'Anonymous activity across all FlyCompare searches. No personal details are shown.'}</p>
        </div>
        <div className="page-head-controls">
          {user && <SegmentedControl label="Data scope" value={scope} onChange={setScope} options={[{ value: 'me', label: 'My searches' }, { value: 'all', label: 'All searches' }]} />}
          <Listbox label="Date range" icon={<CalendarDays size={14} />} value={range} onChange={(v) => setRange(v as AnalyticsRange)} options={RANGES} align="right" />
        </div>
      </div>

      {!user && ready && <Notice>You are viewing anonymous totals for all searches. <button className="link-btn" onClick={() => openAuth('login', 'Sign in to see insights from your own searches.')}><LogIn size={13} /> Sign in</button> to see your personal travel dashboard.</Notice>}
      {error && <Notice kind="error">{error} <button className="link-btn" onClick={() => setReload((n) => n + 1)}><RefreshCw size={13} /> Retry</button></Notice>}
      {loading && !data && <Loading label="Loading insights…" />}

      {data && t && (
        <div className={loading ? 'is-refreshing' : ''}>
          {mix.length > 0 && <p className="data-mix">Searches in this period by data source: {mix.map(([s, n]) => <span key={s}><StatusPill status={s} /> {n}</span>)} — test and demo searches are developer data, not real market activity. Searches are not bookings.</p>}
          <div className="kpi-grid">
            <Kpi icon={<Search size={18} />} label={`Searches · ${rangeLabel}`} value={t.period_searches} note={`${t.all_time_searches} all time`} />
            <Kpi icon={<Globe2 size={18} />} label="Unique destinations" value={t.unique_destinations} note={`${plural(t.unique_routes, 'distinct route')}`} />
            <Kpi icon={<Route size={18} />} label="Most searched route" value={data.most_searched_route ? `${data.most_searched_route.origin} → ${data.most_searched_route.destination}` : '—'} note={data.most_searched_route ? `${plural(data.most_searched_route.count, 'search', 'searches')} · ${Math.round(data.most_searched_route.share * 100)}%` : 'No searches in this period'} />
            <Kpi icon={<BarChart3 size={18} />} label="Avg. offers per search" value={t.average_offers_per_search ?? '—'} note={t.searches_with_no_offers ? `${plural(t.searches_with_no_offers, 'search', 'searches')} returned no offers` : 'Offers returned by the provider'} />
          </div>

          {t.period_searches === 0 ? (
            <div className="card panel insights-empty">
              <EmptyState icon={<BarChart3 size={30} />} title={`No searches ${range === 'all' ? 'yet' : `in the ${rangeLabel}`}`} action={<button className="btn btn-primary" onClick={() => onSearchRoute('KHI', 'DXB')}><Search size={15} /> Run a search</button>}>
                Insights are built only from real searches{effectiveScope === 'me' ? ' you make while signed in' : ''}. {range !== 'all' && 'Try a longer date range, or '}run a search to start your history.
              </EmptyState>
            </div>
          ) : (
            <>
              <div className="insights-grid">
                <Panel title="Search activity" aside={<span className="muted small">{data.activity.granularity === 'day' ? 'Daily' : data.activity.granularity === 'week' ? 'Weekly' : 'Monthly'}</span>}>
                  <ActivityChart data={activity} />
                </Panel>
                <Panel title="Top destinations" aside={<MapPin size={16} className="muted" />}>
                  <TopDestinationBars destinations={data.top_destinations} />
                </Panel>
                <Panel title="Popular routes" aside={<Route size={16} className="muted" />}>
                  <Expandable total={data.top_routes.length} noun="routes">{(limit) => (
                  <ul className="route-list">
                    {data.top_routes.slice(0, limit).map((r, i) => (
                      <li key={`${r.origin}-${r.destination}`}>
                        <span className={`route-rank${i < 3 ? ' top' : ''}`}>{i + 1}</span>
                        <span><b>{r.origin} <ArrowRight size={12} /> {r.destination}</b><small>{r.origin_label} to {r.destination_label}</small></span>
                        <span className="route-count">{r.count}<small>{Math.round(r.share * 100)}% of searches</small></span>
                        {/^[A-Z]{3}$/.test(r.origin) && /^[A-Z]{3}$/.test(r.destination) && <button className="link-btn small" onClick={() => onSearchRoute(r.origin, r.destination)}>Search</button>}
                      </li>
                    ))}
                  </ul>
                  )}</Expandable>
                </Panel>
                <Panel title="Airlines in returned offers" aside={<Plane size={16} className="muted" />}>
                  {data.airlines.items.length
                    ? <Expandable total={data.airlines.items.length} noun="airlines" note={<p className="muted small">{data.airlines.basis}</p>}>{(limit) => (
                        <AirlineOffersChart data={data.airlines.items.map((a) => ({ name: a.airline, value: a.offers, airlineCode: a.airline_code, logoUrl: a.airline_logo_url }))} limit={limit} />
                      )}</Expandable>
                    : <ChartEmpty icon={<Plane />} title="No offer data in this period" text="Airline counts come from stored provider offers. Simulated demo results are not stored." />}
                </Panel>
                <Panel title="Search preferences" aside={<Users size={16} className="muted" />}>
                  <div className="insights-preferences">
                    <div><b>Cabin class</b>{data.cabins.map((c) => <p key={c.cabin}><span>{c.cabin}</span><strong>{c.count} / {t.period_searches} searches</strong></p>)}</div>
                    <div><b>Travellers</b>{data.passengers.map((p) => <p key={p.passengers}><span>{plural(p.passengers, 'traveller')}</span><strong>{p.count} / {t.period_searches} searches</strong></p>)}</div>
                  </div>
                  <p className="muted small">Preferences selected in searches, not confirmed bookings.</p>
                </Panel>
                <Panel title="Popular departure months" aside={<CalendarDays size={16} className="muted" />}>
                  {data.departure_months.length
                    ? <DepartureMonthsChart data={data.departure_months.map((m) => ({ name: new Date(`${m.month}-15T12:00:00`).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' }), value: m.count }))} />
                    : <ChartEmpty icon={<CalendarDays />} title="No departure dates yet" text="Shows which travel months people search most." />}
                </Panel>
                <Panel title="Returned fares" aside={<Wallet size={16} className="muted" />}>
                  <FaresTable fares={data.fares} />
                </Panel>
                <Panel title="Popular travel times" aside={<span className="muted small">By departure date searched</span>}>
                  <Heatmap cells={data.travel_heatmap} />
                  <p className="muted small">Counts reflect searched departure dates, grouped by month and weekday across the selected reporting period. Not bookings or actual departures.</p>
                </Panel>
              </div>
              <PriceTrendPanel recent={data.recent_searches} scope={effectiveScope} />
              <ObservationHistory routes={data.top_routes.filter((r) => /^[A-Z]{3}$/.test(r.origin) && /^[A-Z]{3}$/.test(r.destination)).slice(0, 8)} />
              {effectiveScope === 'me' && data.recent_searches && (
                <Panel title="Recent search activity" aside={<History size={16} className="muted" />}>
                  <div className="table" role="table">
                    <div className="tr th" role="row"><span>Route</span><span>Departure</span><span>Trip</span><span>Travellers</span><span>Offers</span><span>Lowest</span></div>
                    {data.recent_searches.map((h) => (
                      <div className="tr" role="row" key={h.id}>
                        <b>{h.origin_code ?? h.origin} <ArrowRight size={12} /> {h.destination_code ?? h.destination}</b>
                        <span>{dayMonth(h.departure_date)}</span><span>{h.trip_type === 'round-trip' ? 'Round trip' : 'One way'}</span><span>{h.passengers}</span><span>{h.result_count}</span>
                        <span>{h.min_price != null && h.currency ? <><Price amount={h.min_price} currency={h.currency} inline /> <StatusPill status={h.data_status} /></> : '—'}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}


function TopDestinationBars({ destinations }: { destinations: Analytics['top_destinations'] }) {
  if (!destinations.length) return <ChartEmpty icon={<MapPin />} title="No destination data yet" text="Destination shares appear after searches have been recorded." />;
  const maxCount = Math.max(1, ...destinations.map((d) => d.count));
  return (
    <Expandable total={destinations.length} noun="destinations">{(limit) => (
    <div className="top-destination-list">
      {destinations.slice(0, limit).map((d) => {
        const share = Math.max(0, Math.min(1, d.share));
        return (
          <div className="top-destination-row" key={d.code}>
            <div className="top-destination-meta">
              <b title={d.label}>{d.label}</b>
              <span>{d.count.toLocaleString()} {d.count === 1 ? 'search' : 'searches'}</span>
              <strong>{(share * 100).toFixed(share * 100 < 10 ? 1 : 0)}%</strong>
            </div>
            <div className="top-destination-track" role="img" aria-label={`${d.label}: ${d.count} searches, ${(share * 100).toFixed(1)} percent of qualifying searches`}>
              <span style={{ width: `${(d.count / maxCount) * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
    )}</Expandable>
  );
}

const PREVIEW_ROWS = 5;

/** Shows the first few rows of a list with a "View all" toggle. Expanding scrolls the
 *  full list inside the collapsed height, so the panel and the page never grow. */
function Expandable({ total, noun, note, children }: { total: number; noun: string; note?: ReactNode; children: (limit: number) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const [height, setHeight] = useState<number>();
  const body = useRef<HTMLDivElement>(null);
  const canExpand = total > PREVIEW_ROWS;
  const toggle = () => {
    if (!open) setHeight(body.current?.offsetHeight);
    else body.current?.scrollTo({ top: 0 });
    setOpen(!open);
  };
  return (
    <>
      <div ref={body} className={`panel-body${open ? ' is-expanded' : ''}`} style={open && height ? { height, maxHeight: height } : undefined}>
        {children(open ? total : PREVIEW_ROWS)}
      </div>
      {(canExpand || note) && (
        <div className="panel-foot">
          {note}
          {canExpand && (
            <button className="view-more-btn" onClick={toggle} aria-expanded={open}>
              {open ? 'Show less' : `View all ${total} ${noun}`} <ChevronDown size={14} className={open ? 'flip' : ''} />
            </button>
          )}
        </div>
      )}
    </>
  );
}

function Panel({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return <section className="card panel"><div className="panel-head"><h3>{title}</h3>{aside}</div>{children}</section>;
}

function Kpi({ icon, label, value, note }: { icon: ReactNode; label: string; value: string | number; note: string }) {
  return <article className="card kpi"><span className="icon-square">{icon}</span><div><small>{label}</small><strong title={String(value)}>{value}</strong><span className="muted small">{note}</span></div></article>;
}

function ChartEmpty({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return <div className="chart-empty">{icon}<b>{title}</b><span>{text}</span></div>;
}

function FaresTable({ fares }: { fares: Analytics['fares'] }) {
  if (!fares.length) return <ChartEmpty icon={<Wallet />} title="No stored fares in this period" text="Average fares are calculated from stored provider offers. Simulated demo results are never included." />;
  return (
    <>
      <div className="table fares-table">
        <div className="tr th"><span>Currency</span><span>Source</span><span>Avg. offer</span><span>Avg. lowest</span><span>Offers</span></div>
        {fares.map((f) => (
          <div className="tr" key={`${f.currency}-${f.data_status}`}>
            <b>{f.currency}</b><span><StatusPill status={f.data_status} /></span><span><Price amount={f.average_offer_price} currency={f.currency} inline /></span>
            <span>{f.average_lowest_price != null ? <Price amount={f.average_lowest_price} currency={f.currency} inline /> : '—'}</span><span>{f.offers} / {f.searches} {f.searches === 1 ? 'search' : 'searches'}</span>
          </div>
        ))}
      </div>
      <p className="muted small">Avg. offer is the mean across stored offers; avg. lowest is the mean of each search’s cheapest returned offer. These are observed search results, not guaranteed bookable fares. Currency and data source are never combined.</p>
    </>
  );
}

function Heatmap({ cells }: { cells: Analytics['travel_heatmap'] }) {
  const grid = Array.from({ length: 12 }, () => Array(7).fill(0) as number[]);
  cells.forEach((c) => { grid[c.month - 1][c.weekday] = c.count; });
  const max = Math.max(1, ...cells.map((c) => c.count));
  const active = grid.map((r, i) => (r.some(Boolean) ? i : -1)).filter((i) => i >= 0);
  if (!active.length) return <ChartEmpty icon={<CalendarDays />} title="No travel dates yet" text="See which months and weekdays you travel most once you search." />;
  const first = active[0], last = Math.max(active[active.length - 1], Math.min(11, first + 5));
  return (
    <div className="heatmap">
      <div className="heat-row heat-labels"><span />{['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => <span key={i}>{d}</span>)}</div>
      {Array.from({ length: last - first + 1 }, (_, k) => first + k).map((m) => (
        <div className="heat-row" key={m}><span>{MONTHS[m]}</span>{grid[m].map((v, d) => <i key={d} className={v ? 'on' : ''} style={v ? { opacity: 0.3 + (v / max) * 0.7 } : undefined} title={`${MONTHS[m]} · ${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d]}: ${v} search${v === 1 ? '' : 'es'}`} />)}</div>
      ))}
      <div className="heat-legend"><span>Fewer</span><i /><span>More searches</span></div>
    </div>
  );
}

/** Lets the user pick one of their searched trips and shows its observed fare history. */
function PriceTrendPanel({ recent, scope }: { recent?: HistoryItem[]; scope: 'me' | 'all' }) {
  const options = useMemo(() => {
    const seen = new Set<string>();
    return (recent ?? []).filter((h) => h.origin_code && h.destination_code && h.data_status !== 'demo').filter((h) => {
      const k = `${h.origin_code}-${h.destination_code}-${h.departure_date}-${h.return_date}-${h.cabin}-${h.passengers}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [recent]);
  const [choice, setChoice] = useState(0);
  const [data, setData] = useState<PriceHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pick = options[choice];
  useEffect(() => {
    setData(null);
    setError(null);
    if (!pick) return;
    const p = new URLSearchParams({ origin: pick.origin_code!, destination: pick.destination_code!, departure_date: pick.departure_date, cabin: pick.cabin, trip_type: pick.trip_type, passengers: String(pick.passengers) });
    if (pick.return_date) p.set('return_date', pick.return_date);
    api<PriceHistory>(`/api/prices/history?${p}`).then(setData).catch((err) => setError(errorText(err)));
  }, [pick]);

  const group = data?.groups[0];
  const cur = useDisplayCurrency(group?.currency);
  const calendar = useNearbyDateFares(pick, group?.currency, group?.data_status);
  const hasTrend = (group?.points.length ?? 0) > 1;
  const [view, setView] = useState<'dates' | 'time'>('dates');
  const shownView = hasTrend ? view : 'dates';
  return (
    <section className="card panel trend-panel">
      <div className="panel-head">
        <h3><LineIcon size={16} /> Price trends</h3>
        {options.length > 0 && (
          <Listbox label="Trip to show" value={String(choice)} onChange={(v) => setChoice(Number(v))} align="right"
            options={options.map((h, i) => ({ value: String(i), label: `${h.origin_code} → ${h.destination_code} · ${dayMonth(h.departure_date)}${h.return_date ? `–${dayMonth(h.return_date)}` : ''}`, hint: h.cabin }))} />
        )}
      </div>
      {scope === 'all' || !options.length ? (
        <ChartEmpty icon={<LineIcon />} title="Price trends come from repeated searches" text={scope === 'all' ? 'Sign in and search the same trip on different days to build a genuine price history for it.' : 'Search a trip with the live or test provider; repeat the search on later days to build its price history.'} />
      ) : error ? <Notice kind="error">{error}</Notice> : !data ? <Loading /> : !group ? (
        <ChartEmpty icon={<Info />} title="No observations for this trip" text="No provider offers were stored for this exact trip." />
      ) : group.points.length > 0 ? (
        <>
          <div className="trend-stats">
            <div><small>Latest lowest fare</small><strong>{cur.format(group.points[group.points.length - 1].lowest_price)}</strong>{cur.approx && <span className="muted small">{money(group.points[group.points.length - 1].lowest_price, group.currency)} original</span>}</div>
            <div><small>Cheapest seen</small><strong>{cur.format(Math.min(...group.points.map((p) => p.lowest_price)))}</strong>{calendar?.cheapest && calendar.cheapest.date !== pick!.departure_date && <span className="muted small">{cur.format(calendar.cheapest.price)} on {dayMonth(calendar.cheapest.date)} nearby</span>}</div>
            <div><small>Observations</small><strong>{plural(group.points.length, 'search', 'searches')}</strong><span className="muted small">over {plural(group.distinct_days, 'day')}</span></div>
            <div><small>Data source</small><StatusPill status={group.data_status} /></div>
          </div>
          <div className="trend-toolbar">
            <SegmentedControl label="Price graph" value={shownView} onChange={setView} options={[
              { value: 'dates', label: 'By departure date' },
              { value: 'time', label: hasTrend ? 'Over time' : 'Over time (needs 2+ searches)' },
            ]} />
            {shownView === 'dates' && <span className="trend-legend"><i className="sel" />Your date<i className="low" />Cheapest<i />Other dates</span>}
          </div>
          {shownView === 'time'
            ? <PriceTrendChart points={group.points.map((p) => ({ ...p, lowest_price: cur.value(p.lowest_price) }))} currency={cur.currency} height={230} />
            : calendar && calendar.days.some((d) => d.price != null)
              ? <DepartureFareChart days={calendar.days.map((d) => ({ ...d, price: d.price == null ? null : cur.value(d.price) }))} selected={pick!.departure_date} currency={cur.currency} />
              : calendar === undefined ? <Loading /> : <ChartEmpty icon={<CalendarDays />} title="No nearby fares yet" text="Search this route on a few nearby dates to compare prices by departure day." />}
          <p className="muted small">
            {shownView === 'time'
              ? 'Lowest fare returned in each search for this exact trip.'
              : `Lowest fare seen for each departure date within ${NEARBY_DAYS} days of your trip, from comparable searches. Gaps are dates nobody has searched yet.`}
            {cur.approx ? ` Shown in ${cur.currency}, converted from ${group.currency} (${cur.source}); approximate.` : ` In ${group.currency}.`}
            {group.data_status === 'test' ? ' Sandbox prices are not real market fares.' : ''}
          </p>
          {!group.sufficient_for_trend && (
            <div className="trend-wait">
              <div className="trend-progress"><span style={{ width: `${Math.min(100, (group.distinct_days / data.requirements.min_distinct_days) * 100)}%` }} /></div>
              <p className="muted small">
                {group.points.length} of {data.requirements.min_points} searches across {group.distinct_days} of {data.requirements.min_distinct_days} days collected. Repeat this search on different days to build a reliable trend.
              </p>
            </div>
          )}
        </>
      ) : (
        <ChartEmpty
          icon={<Info />}
          title="Waiting for fare observations"
          text="Search this exact trip to start collecting fare observations."
        />
      )}
    </section>
  );
}

const NEARBY_DAYS = 14;
type FareCalendar = { groups: { currency: string; data_status: string; days: Record<string, { lowest_price: number; stale: boolean }> }[] };
const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const shiftDay = (iso: string, n: number) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() + n); return isoDay(d); };

/**
 * Lowest fare seen for each departure date within ±NEARBY_DAYS of a searched trip,
 * from comparable searches (same route, trip type, cabin and travellers) in the
 * same currency and data source. undefined while loading.
 */
function useNearbyDateFares(pick: HistoryItem | undefined, currency: string | undefined, status: string | undefined) {
  const [cal, setCal] = useState<FareCalendar | null | undefined>(undefined);
  useEffect(() => {
    setCal(undefined);
    if (!pick || !currency) return;
    const today = todayIso();
    const start = shiftDay(pick.departure_date, -NEARBY_DAYS), end = shiftDay(pick.departure_date, NEARBY_DAYS);
    if (end < today) { setCal(null); return; }
    const p = new URLSearchParams({
      origin: pick.origin_code!, destination: pick.destination_code!, start: start < today ? today : start, end,
      trip_type: pick.trip_type === 'round-trip' ? 'round-trip' : 'one-way', cabin: pick.cabin,
      passengers: String(pick.passengers), children: String(pick.children ?? 0), infants: String(pick.infants ?? 0),
    });
    const ctrl = new AbortController();
    api<FareCalendar>(`/api/prices/calendar?${p}`, { signal: ctrl.signal }).then(setCal).catch(() => { if (!ctrl.signal.aborted) setCal(null); });
    return () => ctrl.abort();
  }, [pick, currency]);

  return useMemo(() => {
    if (cal === undefined || !pick) return undefined;
    const g = cal?.groups.find((x) => x.currency === currency && x.data_status === status);
    const days = Array.from({ length: NEARBY_DAYS * 2 + 1 }, (_, i) => {
      const date = shiftDay(pick.departure_date, i - NEARBY_DAYS);
      const f = g?.days[date];
      return { date, price: f ? f.lowest_price : null, stale: f?.stale };
    });
    // The trip's own search always counts, even if the calendar has not picked it up.
    const own = days[NEARBY_DAYS];
    if (own.price == null && pick.min_price != null && pick.currency === currency) own.price = pick.min_price;
    const priced = days.filter((d) => d.price != null) as { date: string; price: number }[];
    const cheapest = priced.length ? priced.reduce((a, b) => (b.price < a.price ? b : a)) : null;
    return { days, cheapest };
  }, [cal, pick, currency, status]);
}

/** Lowest observed fare per day for a popular route, across all searched travel dates. */
function ObservationHistory({ routes }: { routes: Analytics['top_routes'] }) {
  const [choice, setChoice] = useState(0);
  const [data, setData] = useState<RouteDailyHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pick = routes[choice];
  useEffect(() => {
    setData(null);
    setError(null);
    if (!pick) return;
    api<RouteDailyHistory>(`/api/prices/route-history?origin=${pick.origin}&destination=${pick.destination}`).then(setData).catch((err) => setError(errorText(err)));
  }, [pick?.origin, pick?.destination]); // eslint-disable-line react-hooks/exhaustive-deps
  const group = data?.groups[0];
  const cur = useDisplayCurrency(group?.currency);
  if (!routes.length) return null;
  return (
    <section className="card panel trend-panel">
      <div className="panel-head">
        <div><h3><LineIcon size={16} /> Fare observation history</h3><p className="muted small">{data?.basis ?? 'Lowest offer observed each day for this route.'}</p></div>
        <Listbox label="Route" value={String(choice)} onChange={(v) => setChoice(Number(v))} align="right"
          options={routes.map((r, i) => ({ value: String(i), label: `${r.origin} → ${r.destination}`, hint: `${r.origin_label} to ${r.destination_label}` }))} />
      </div>
      {error ? <Notice kind="error">{error}</Notice> : !data ? <Loading /> : !group ? (
        <ChartEmpty icon={<LineIcon />} title="No fares observed for this route" text="Fares are recorded from live or test provider searches. Simulated demo results are never stored." />
      ) : group.sufficient_for_trend ? (
        <>
          <DailyPriceChart points={group.points.map((p) => ({ ...p, lowest_price: cur.value(p.lowest_price) }))} currency={cur.currency} />
          <p className="muted small">{group.points.length} days with observations · {cur.approx ? `≈ ${cur.currency}, converted from ${group.currency}` : group.currency} ·<StatusPill status={group.data_status} />{group.data_status === 'test' ? ' Sandbox prices are not real market fares.' : ''} Travel dates differ between days, so this is not a forecast.</p>
        </>
      ) : (
        <div className="trend-wait">
          <div className="trend-progress"><span style={{ width: `${Math.min(100, (group.points.length / data.requirements.min_days) * 100)}%` }} /></div>
          <p><b>{group.points.length} of {data.requirements.min_days} days</b> with observations so far for this route ({group.currency}).</p>
          <p className="muted small">A history is only drawn once fares have been observed on at least {data.requirements.min_days} different days.</p>
        </div>
      )}
    </section>
  );
}
