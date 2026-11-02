// Pure filtering, sorting and ranking of the offers returned by a search.
// Everything here operates only on the actual result set.

import { bagOf, legsOf, timeOf } from './format';
import type { Flight } from './types';

export type Sort = 'recommended' | 'cheapest' | 'fastest';
export type StopKey = 'direct' | 'one' | 'two';
export type TimeWindow = 'night' | 'morning' | 'afternoon' | 'evening';
export const TIME_WINDOWS: [TimeWindow, string, string][] = [
  ['night', 'Night', '00:00–05:59'], ['morning', 'Morning', '06:00–11:59'], ['afternoon', 'Afternoon', '12:00–17:59'], ['evening', 'Evening', '18:00–23:59'],
];
/** Local time window of an ISO time (airport-local, as the provider sends it). */
export function windowOf(iso: string): TimeWindow {
  const hour = Number(timeOf(iso).slice(0, 2));
  return hour < 6 ? 'night' : hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
}
const outbound = (f: Flight) => legsOf(f)[0];
export type Filters = {
  stops: StopKey[];
  airlines: string[];
  maxPrice: number | null;
  maxDuration: number | null;
  carryOn: boolean;
  checked: boolean;
  refundableOnly: boolean;
  departs: TimeWindow[]; // outbound departure, local time
  arrives: TimeWindow[]; // outbound arrival, local time
};
export const emptyFilters: Filters = { stops: [], airlines: [], maxPrice: null, maxDuration: null, carryOn: false, checked: false, refundableOnly: false, departs: [], arrives: [] };

/** Stops of the outbound journey. */
export const stopsOf = (f: Flight) => f.itineraries?.[0]?.stops ?? f.stops;
/** Total travel time across all journeys (outbound + return). */
export const totalDurationOf = (f: Flight) => legsOf(f).reduce((sum, leg) => sum + (leg.duration_minutes ?? 0), 0) || f.duration_minutes;
/** The most stops on any journey of the trip. */
export const maxStopsOf = (f: Flight) => Math.max(...legsOf(f).map((l) => l.stops));
export const stopKey = (n: number): StopKey => n === 0 ? 'direct' : n === 1 ? 'one' : 'two';
export const hasChecked = (f: Flight) => (f.baggage_kg ?? 0) > 0 || (bagOf(f, 'checked')?.quantity ?? 0) > 0;
export const hasCarryOn = (f: Flight) => (bagOf(f, 'carry_on')?.quantity ?? 0) > 0;

export function applyFilters(results: Flight[], f: Filters): Flight[] {
  return results.filter((r) =>
    (!f.stops.length || f.stops.includes(stopKey(maxStopsOf(r)))) &&
    (!f.airlines.length || f.airlines.includes(r.airline)) &&
    (f.maxPrice == null || r.price <= f.maxPrice) &&
    (f.maxDuration == null || totalDurationOf(r) <= f.maxDuration) &&
    (!f.carryOn || hasCarryOn(r)) &&
    (!f.checked || hasChecked(r)) &&
    (!f.refundableOnly || r.refundable === true) &&
    (!f.departs?.length || f.departs.includes(windowOf(outbound(r).departing_at))) &&
    (!f.arrives?.length || f.arrives.includes(windowOf(outbound(r).arriving_at))),
  );
}

export const activeFilterCount = (f: Filters) =>
  f.stops.length + f.airlines.length + (f.maxPrice != null ? 1 : 0) + (f.maxDuration != null ? 1 : 0) + Number(f.carryOn) + Number(f.checked) + Number(f.refundableOnly) + (f.departs?.length ?? 0) + (f.arrives?.length ?? 0);

/**
 * Recommendation score (lower is better), defined on the current result set:
 *   50% price + 25% total journey time (incl. connections) + 10% stops
 *   + 10% checked baggage + 5% refundability
 * Price, time and stops are min–max normalised to 0–1 across the results being
 * ranked (cheapest = 0, most expensive = 1). Baggage and refundability are
 * 0 when included/refundable, 1 when the provider says they are not, and 0.5
 * when the provider did not say: unknown is neither rewarded nor treated as "no".
 */
export const SCORE_WEIGHTS = { price: 0.5, duration: 0.25, stops: 0.1, bags: 0.1, flex: 0.05 } as const;

export type ScoreParts = { price: number; duration: number; stops: number; bags: number; flex: number; total: number };

const bagScore = (f: Flight) => {
  const checked = bagOf(f, 'checked');
  if (checked?.quantity != null) return checked.quantity > 0 ? 0 : 1;
  if ((f.baggage_kg ?? 0) > 0) return 0;
  return f.baggage_allowances?.length ? 1 : 0.5; // bags listed without a checked bag = not included
};
const flexScore = (f: Flight) => (f.refundable == null ? 0.5 : f.refundable ? 0 : 1);

export function scoreResults(results: Flight[]): Map<string, ScoreParts> {
  const scores = new Map<string, ScoreParts>();
  if (!results.length) return scores;
  const prices = results.map((r) => r.price), durations = results.map(totalDurationOf), stops = results.map(maxStopsOf);
  const range = (xs: number[]) => [Math.min(...xs), Math.max(...xs)] as const;
  const [pMin, pMax] = range(prices), [dMin, dMax] = range(durations), [sMin, sMax] = range(stops);
  const norm = (v: number, lo: number, hi: number) => hi === lo ? 0 : (v - lo) / (hi - lo);
  for (const r of results) {
    const price = norm(r.price, pMin, pMax), duration = norm(totalDurationOf(r), dMin, dMax), stop = norm(maxStopsOf(r), sMin, sMax);
    const bags = bagScore(r), flex = flexScore(r);
    const total = price * SCORE_WEIGHTS.price + duration * SCORE_WEIGHTS.duration + stop * SCORE_WEIGHTS.stops + bags * SCORE_WEIGHTS.bags + flex * SCORE_WEIGHTS.flex;
    scores.set(r.id, { price, duration, stops: stop, bags, flex, total });
  }
  return scores;
}

export function sortResults(results: Flight[], sort: Sort, scores = scoreResults(results)): Flight[] {
  const list = [...results];
  // Ties fall back to price, then duration, so ordering is deterministic.
  const tie = (a: Flight, b: Flight) => a.price - b.price || totalDurationOf(a) - totalDurationOf(b) || a.id.localeCompare(b.id);
  if (sort === 'cheapest') return list.sort((a, b) => a.price - b.price || totalDurationOf(a) - totalDurationOf(b) || a.id.localeCompare(b.id));
  if (sort === 'fastest') return list.sort((a, b) => totalDurationOf(a) - totalDurationOf(b) || tie(a, b));
  return list.sort((a, b) => (scores.get(a.id)?.total ?? 0) - (scores.get(b.id)?.total ?? 0) || tie(a, b));
}

export function facets(results: Flight[]) {
  const stops: Record<StopKey, number> = { direct: 0, one: 0, two: 0 };
  const airlines = new Map<string, number>();
  const logos = new Map<string, string>();
  const departs: Record<TimeWindow, number> = { night: 0, morning: 0, afternoon: 0, evening: 0 };
  const arrives: Record<TimeWindow, number> = { night: 0, morning: 0, afternoon: 0, evening: 0 };
  for (const r of results) {
    stops[stopKey(maxStopsOf(r))]++;
    airlines.set(r.airline, (airlines.get(r.airline) ?? 0) + 1);
    if (r.airline_logo_url && !logos.has(r.airline)) logos.set(r.airline, r.airline_logo_url);
    departs[windowOf(outbound(r).departing_at)]++;
    arrives[windowOf(outbound(r).arriving_at)]++;
  }
  const prices = results.map((r) => r.price), durations = results.map(totalDurationOf);
  return {
    stops,
    airlines: [...airlines.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])),
    priceMin: prices.length ? Math.floor(Math.min(...prices)) : 0,
    priceMax: prices.length ? Math.ceil(Math.max(...prices)) : 0,
    durationMax: durations.length ? Math.ceil(Math.max(...durations) / 30) * 30 : 0,
    currencies: [...new Set(results.map((r) => r.currency))],
    refundableKnown: results.some((r) => r.refundable != null),
    refundableCount: results.filter((r) => r.refundable === true).length,
    carryOnCount: results.filter(hasCarryOn).length,
    checkedCount: results.filter(hasChecked).length,
    logos,
    departs,
    arrives,
  };
}
