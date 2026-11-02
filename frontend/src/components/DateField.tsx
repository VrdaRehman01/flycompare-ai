import { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, CalendarDays, ChevronLeft, ChevronRight, Info, Plane, Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import { addDays, addMonths, cheapestIn, compactPrice, inRange, monthBounds, monthGrid, nightsBetween, parseIso } from '../lib/calendar';
import { money, relativeTime, shortDate, todayIso } from '../lib/format';
import type { Cabin, Passengers } from '../lib/types';
import { StatusPill } from './ui';

/** Route context that lets the calendar show fares seen in earlier, comparable searches. */
export type FareContext = { origin: string; destination: string; tripType: 'one-way' | 'round-trip'; cabin: Cabin; passengers: Passengers };
type DayFare = { lowest_price: number; observed_at: string; stale: boolean; airline: string; stops: number; return_date: string | null; tier: 'low' | 'mid' | 'high' | null };
type CalendarData = {
  basis: string; rules: { stale_after_days: number; min_dates_for_comparison: number };
  groups: { currency: string; data_status: string; days: Record<string, DayFare>; months: { month: string; lowest_price: number; dates_observed: number }[]; cheapest_month: string | null; tiers_available: boolean }[];
};
type Mode = 'exact' | 'flex' | 'month';
const FLEX_DAYS = 3;
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const longDate = (d: string) => parseIso(d).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const monthName = (y: number, m: number, style: 'long' | 'short' = 'long') => new Date(y, m, 1).toLocaleDateString('en-GB', { month: style, year: 'numeric' });

const fareCache = new Map<string, Promise<CalendarData>>();
function useFareCalendar(ctx: FareContext | null | undefined, active: boolean) {
  const [data, setData] = useState<CalendarData | null>(null);
  const url = ctx && ctx.origin && ctx.destination
    ? `/api/prices/calendar?${new URLSearchParams({
      origin: ctx.origin, destination: ctx.destination, start: todayIso(), end: addDays(todayIso(), 365), trip_type: ctx.tripType, cabin: ctx.cabin,
      passengers: String(ctx.passengers.adults), children: String(ctx.passengers.childAges.length), infants: String(ctx.passengers.infants),
    })}`
    : null;
  useEffect(() => {
    if (!active || !url) { setData(null); return; }
    let live = true;
    if (!fareCache.has(url)) fareCache.set(url, api<CalendarData>(url).catch((e) => { fareCache.delete(url); throw e; }));
    fareCache.get(url)!.then((d) => { if (live) setData(d); }).catch(() => { if (live) setData(null); });
    return () => { live = false; };
  }, [url, active]);
  return url ? data : null;
}

function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return { open, setOpen, ref };
}

/**
 * FlyCompare date picker. Shows a ticket-style summary of the chosen dates and
 * two months of days. With a route chosen, each day can carry the lowest fare
 * seen for it in earlier comparable searches, labelled as an observation.
 * "±3 days" and "Whole month" help choose a date; the search still runs on the
 * exact date chosen, because the provider prices one date at a time.
 */
export function DateField({ label, start, end, range, min, onChange, error, endLabel = 'Return', fares }: {
  label: string; start: string; end?: string; range?: boolean; min?: string; onChange: (start: string, end: string) => void; error?: string; endLabel?: string;
  fares?: FareContext | null;
}) {
  const id = useId();
  const { open, setOpen, ref } = usePopover();
  const today = todayIso();
  const minDate = min && min > today ? min : today;
  const base = parseIso(start || minDate);
  const [view, setView] = useState({ year: base.getFullYear(), month: base.getMonth() });
  const [picking, setPicking] = useState<'start' | 'end'>('start');
  const [hover, setHover] = useState('');
  const [focusDay, setFocusDay] = useState(start || minDate);
  const [mode, setMode] = useState<Mode>('exact');
  const grid = useRef<HTMLDivElement>(null);
  const data = useFareCalendar(fares, open);
  const group = data?.groups[0];
  const otherGroups = (data?.groups.length ?? 0) - 1;

  useEffect(() => {
    if (!open) return;
    const b = parseIso(start || minDate);
    setView({ year: b.getFullYear(), month: b.getMonth() });
    setPicking('start');
    setFocusDay(start || minDate);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (open && mode !== 'month') grid.current?.querySelector<HTMLButtonElement>(`[data-day="${focusDay}"]`)?.focus(); }, [open, focusDay, view, mode]);

  const finishIfDone = (s: string, e: string) => { if (!range || e) setOpen(false); else setPicking('end'); onChange(s, e); };
  const pick = (day: string) => {
    if (!range) { onChange(day, ''); setOpen(false); return; }
    if (picking === 'start' || (start && day < start)) {
      // Keep the trip length when moving the departure of an existing round trip.
      const keep = start && end ? nightsBetween(start, end) : 0;
      onChange(day, keep ? addDays(day, keep) : '');
      setPicking('end');
      return;
    }
    finishIfDone(start, day);
  };
  const showMonthOf = (day: string) => {
    const d = parseIso(day);
    const idx = d.getFullYear() * 12 + d.getMonth();
    if (idx < view.year * 12 + view.month || idx > view.year * 12 + view.month + 1) setView({ year: d.getFullYear(), month: d.getMonth() });
  };
  const moveFocus = (next: string) => {
    if (next < minDate) next = minDate;
    setFocusDay(next);
    showMonthOf(next);
  };
  const onGridKey = (e: React.KeyboardEvent) => {
    const d = parseIso(focusDay);
    const steps: Record<string, () => string> = {
      ArrowLeft: () => addDays(focusDay, -1), ArrowRight: () => addDays(focusDay, 1), ArrowUp: () => addDays(focusDay, -7), ArrowDown: () => addDays(focusDay, 7),
      Home: () => addDays(focusDay, -((d.getDay() + 6) % 7)), End: () => addDays(focusDay, 6 - ((d.getDay() + 6) % 7)),
      PageUp: () => shiftMonth(-1), PageDown: () => shiftMonth(1),
    };
    if (e.key in steps) { e.preventDefault(); moveFocus(steps[e.key]()); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(focusDay); }
  };
  const shiftMonth = (n: number) => {
    const d = parseIso(focusDay);
    const target = new Date(d.getFullYear(), d.getMonth() + n, 1);
    const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    target.setDate(Math.min(d.getDate(), last));
    return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
  };
  const minIdx = parseIso(minDate).getFullYear() * 12 + parseIso(minDate).getMonth();
  const canPrev = view.year * 12 + view.month > minIdx;
  const rangeEnd = picking === 'end' && hover && hover > start ? hover : end ?? '';
  const nights = nightsBetween(start, range ? rangeEnd : '');

  // Flexible window around the chosen departure (or return when picking it).
  const flexAnchor = picking === 'end' && end ? end : start;
  const flexFrom = flexAnchor ? (addDays(flexAnchor, -FLEX_DAYS) < minDate ? minDate : addDays(flexAnchor, -FLEX_DAYS)) : '';
  const flexTo = flexAnchor ? addDays(flexAnchor, FLEX_DAYS) : '';
  const flexBest = mode === 'flex' && flexAnchor && picking === 'start' ? cheapestIn(group?.days, flexFrom, flexTo) : null;
  const viewBounds = monthBounds(view.year, view.month);
  const monthBest = mode === 'exact' && group ? cheapestIn(group.days, viewBounds.first < minDate ? minDate : viewBounds.first, monthBounds(addMonths(view.year, view.month, 1).year, addMonths(view.year, view.month, 1).month).last) : null;

  const chooseDate = (day: string) => {
    if (!range) { onChange(day, ''); setOpen(false); return; }
    const keep = start && end ? nightsBetween(start, end) : 0;
    const ret = keep ? addDays(day, keep) : end && end >= day ? end : '';
    onChange(day, ret);
    if (ret) setOpen(false); else setPicking('end');
  };

  const display = (value: string, placeholder: string) => <span className={`field-value ${value ? '' : 'placeholder'}`}><CalendarDays size={16} />{value ? shortDate(value) : placeholder}</span>;
  const fareLabel = (f: DayFare | undefined) => (f && group ? `, lowest fare seen ${money(f.lowest_price, group.currency)} ${relativeTime(f.observed_at)}${group.data_status !== 'live' ? ` (${group.data_status} data)` : ''}` : '');

  return (
    <div className={`date-wrap ${range ? 'is-range' : ''}`} ref={ref}>
      <div className={`field date-field ${error ? 'invalid' : ''}`}>
        <button type="button" id={id} className="date-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <span className="date-part"><small>{label}</small>{display(start, 'Add date')}</span>
          {range && <span className="date-part"><small>{endLabel}</small>{display(end ?? '', 'Add date')}</span>}
        </button>
        {error && <small className="field-error">{error}</small>}
      </div>
      {open && (
        <div className="fc-cal" role="dialog" aria-label={range ? 'Choose departure and return dates' : `Choose ${label.toLowerCase()} date`}>
          <div className="fc-ticket">
            <button type="button" className={`fc-slot ${picking === 'start' ? 'active' : ''}`} onClick={() => setPicking('start')} aria-pressed={picking === 'start'}>
              <small>{label}</small><b>{start ? shortDate(start) : 'Choose a date'}</b>
            </button>
            {range && (
              <>
                <span className="fc-route" aria-hidden="true"><i /><Plane size={14} /><i /><small>{nights ? `${nights} night${nights === 1 ? '' : 's'}` : ''}</small></span>
                <button type="button" className={`fc-slot ${picking === 'end' ? 'active' : ''}`} onClick={() => start && setPicking('end')} aria-pressed={picking === 'end'} disabled={!start}>
                  <small>{endLabel}</small><b>{end ? shortDate(end) : start ? 'Choose a date' : '—'}</b>
                </button>
              </>
            )}
          </div>

          <div className="fc-modes" role="radiogroup" aria-label="Date flexibility">
            {([['exact', 'Exact dates'], ['flex', `± ${FLEX_DAYS} days`], ['month', 'Whole month']] as [Mode, string][]).map(([m, l]) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>{l}</button>
            ))}
          </div>

          {mode === 'month' ? (
            <div className="fc-month-list">
              {Array.from({ length: 12 }, (_, i) => addMonths(parseIso(minDate).getFullYear(), parseIso(minDate).getMonth(), i)).map(({ year, month }) => {
                const key = `${year}-${String(month + 1).padStart(2, '0')}`;
                const summary = group?.months.find((m) => m.month === key);
                const cheapest = group?.cheapest_month === key;
                return (
                  <button key={key} type="button" className={`fc-month-tile ${cheapest ? 'cheapest' : ''}`}
                    onClick={() => { setView({ year, month }); setMode('exact'); const { first } = monthBounds(year, month); setFocusDay(first < minDate ? minDate : first); }}>
                    <b>{monthName(year, month, 'short')}</b>
                    {summary ? <span>from <strong>{money(summary.lowest_price, group!.currency)}</strong><small>{summary.dates_observed} date{summary.dates_observed === 1 ? '' : 's'} seen</small></span> : <small>{fares ? 'No fares seen yet' : 'Choose a route to see fares'}</small>}
                    {cheapest && <em><Sparkles size={11} /> Lowest observed month</em>}
                  </button>
                );
              })}
            </div>
          ) : (
            <>
              <div className="fc-nav">
                <button type="button" className="icon-btn" onClick={() => setView(addMonths(view.year, view.month, -1))} disabled={!canPrev} aria-label="Previous month"><ChevronLeft size={16} /></button>
                <span className="fc-nav-title">{range ? (picking === 'start' ? `Choose ${label.toLowerCase()}` : `Choose ${endLabel.toLowerCase()}`) : `Choose ${label.toLowerCase()} date`}</span>
                <button type="button" className="icon-btn" onClick={() => setView(addMonths(view.year, view.month, 1))} aria-label="Next month"><ChevronRight size={16} /></button>
              </div>
              <div className="fc-months" ref={grid} onKeyDown={onGridKey}>
                {[0, 1].map((offset) => {
                  const m = addMonths(view.year, view.month, offset);
                  return (
                    <div key={offset} className={`fc-month ${offset ? 'second' : ''}`}>
                      <div className="fc-month-title">{monthName(m.year, m.month)}</div>
                      <div className="fc-grid" role="grid" aria-label={monthName(m.year, m.month)}>
                        {WEEKDAYS.map((w) => <span key={w} className="fc-dow" role="columnheader">{w}</span>)}
                        {monthGrid(m.year, m.month).flat().map((day, i) => {
                          if (!day) return <span key={`e${i}`} />;
                          const disabled = day < minDate || (!!range && picking === 'end' && !!start && day < start);
                          const fare = !disabled ? group?.days[day] : undefined;
                          const classes = [
                            'fc-day', day === today ? 'today' : '', day === start ? 'start' : '', range && day === rangeEnd ? 'end' : '',
                            range && inRange(day, start, rangeEnd) ? 'in-range' : '',
                            mode === 'flex' && flexAnchor && day >= flexFrom && day <= flexTo ? 'flex' : '',
                            fare ? `has-fare tier-${fare.tier ?? 'none'}` : '', fare?.stale ? 'stale' : '',
                            flexBest?.date === day ? 'best' : '',
                          ].filter(Boolean).join(' ');
                          return (
                            <button type="button" key={day} data-day={day} role="gridcell" tabIndex={day === focusDay ? 0 : -1} disabled={disabled}
                              aria-selected={day === start || day === end} aria-label={`${longDate(day)}${fareLabel(fare)}`} className={classes}
                              onMouseEnter={() => setHover(day)} onFocus={() => setHover(day)} onClick={() => pick(day)}>
                              <span className="n">{Number(day.slice(8))}</span>
                              {fare && <span className="p">{compactPrice(fare.lowest_price)}</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {mode === 'flex' && (
            <div className="fc-insight">
              {!start ? <span><Info size={14} /> Pick a departure date first; we'll compare the {FLEX_DAYS * 2 + 1} days around it.</span>
                : flexBest && group ? (
                  <>
                    <span><Sparkles size={14} /> Lowest seen within ± {FLEX_DAYS} days: <b>{shortDate(flexBest.date)} · {money(flexBest.info.lowest_price, group.currency)}</b> <small>seen {relativeTime(flexBest.info.observed_at)}</small></span>
                    {flexBest.date !== start && <button type="button" className="btn btn-soft small" onClick={() => chooseDate(flexBest.date)}>Use this date</button>}
                  </>
                ) : <span><Info size={14} /> No fares have been seen for these dates yet. Searching will check live availability for your exact date.</span>}
            </div>
          )}
          {mode === 'exact' && monthBest && group && monthBest.date !== start && (
            <div className="fc-insight subtle">
              <span>Lowest seen in these two months: <b>{shortDate(monthBest.date)} · {money(monthBest.info.lowest_price, group.currency)}</b></span>
              <button type="button" className="link-btn small" onClick={() => { setFocusDay(monthBest.date); chooseDate(monthBest.date); }}>Use it</button>
            </div>
          )}

          <div className="fc-foot">
            {group ? (
              <div className="fc-legend">
                {group.tiers_available
                  ? <><span><i className="dot low" /> Lower</span><span><i className="dot mid" /> Typical</span><span><i className="dot high" /> Higher</span></>
                  : <span><i className="dot mid" /> Fare seen</span>}
                <span><i className="dot none" /> No data</span>
                <span className="fc-source">Lowest {group.currency} fares from earlier searches, not live prices <StatusPill status={group.data_status} />{otherGroups > 0 ? ` · +${otherGroups} other currency/source hidden` : ''}</span>
              </div>
            ) : (
              <span className="muted small">{fares ? (data ? 'No comparable fares seen for this route yet.' : 'Checking fares seen in earlier searches…') : 'Choose a route to see fares from earlier searches.'}</span>
            )}
            <div className="fc-actions">
              {mode === 'month' && <button type="button" className="link-btn small" onClick={() => setMode('exact')}><ArrowLeft size={13} /> Back to days</button>}
              {(start || end) && <button type="button" className="link-btn small" onClick={() => { onChange('', ''); setPicking('start'); }}>Clear</button>}
              <button type="button" className="btn btn-primary small" onClick={() => setOpen(false)}>Done</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
