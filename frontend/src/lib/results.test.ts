import { describe, expect, it } from 'vitest';
import { activeFilterCount, applyFilters, emptyFilters, facets, scoreResults, sortResults, totalDurationOf } from './results';
import type { Flight, Itinerary } from './types';

const leg = (stops: number, minutes: number, from = 'KHI', to = 'DXB'): Itinerary => ({
  origin: from, destination: to, departing_at: '2026-12-10T08:00:00+05:00', arriving_at: '2026-12-10T10:00:00+04:00', duration_minutes: minutes, stops, segments: [],
});

function flight(id: string, price: number, opts: Partial<Flight> & { legs?: Itinerary[] } = {}): Flight {
  return {
    id, provider: 'Duffel', data_status: 'test', retrieved_at: '2026-10-31T00:00:00Z', airline: 'Air A', flight_number: 'AA1',
    origin: 'KHI', destination: 'DXB', departure_date: '2026-12-10', departure_time: '08:00', arrival_time: '10:00',
    duration_minutes: 120, stops: 0, price, currency: 'USD', baggage_kg: null, cabin: 'Economy', refundable: null, disclaimer: '',
    itineraries: opts.legs ?? [leg(0, 120), leg(0, 125, 'DXB', 'KHI')], baggage_allowances: [], ...opts,
  };
}

const results = [
  flight('cheap-slow', 100, { legs: [leg(1, 600), leg(1, 620, 'DXB', 'KHI')], airline: 'Air B' }),
  flight('mid-direct', 150, { refundable: true, baggage_allowances: [{ baggage_type: 'checked', quantity: 1 }, { baggage_type: 'carry_on', quantity: 1 }] }),
  flight('pricey-fast', 400, { legs: [leg(0, 110), leg(0, 110, 'DXB', 'KHI')], refundable: false }),
  flight('two-stops', 120, { legs: [leg(2, 900), leg(0, 130, 'DXB', 'KHI')], airline: 'Air B' }),
];

describe('sorting', () => {
  it('sorts cheapest by price', () => {
    expect(sortResults(results, 'cheapest').map((r) => r.id)).toEqual(['cheap-slow', 'two-stops', 'mid-direct', 'pricey-fast']);
  });
  it('sorts fastest by total journey time across both directions', () => {
    expect(totalDurationOf(results[0])).toBe(1220);
    expect(sortResults(results, 'fastest')[0].id).toBe('pricey-fast');
  });
  it('recommended uses the documented 50/25/10/10/5 weighting', () => {
    const scores = scoreResults(results);
    const s = scores.get('mid-direct')!;
    expect(s.total).toBeCloseTo(s.price * 0.5 + s.duration * 0.25 + s.stops * 0.1 + s.bags * 0.1 + s.flex * 0.05);
    // Included checked bag and refundable fare score 0; unknown scores 0.5; "not refundable" 1.
    expect([s.bags, s.flex]).toEqual([0, 0]);
    expect(scores.get('cheap-slow')!.flex).toBe(0.5);
    expect(scores.get('pricey-fast')!.flex).toBe(1);
    // Cheapest offer gets 0 on price, most expensive 1.
    expect(scores.get('cheap-slow')!.price).toBe(0);
    expect(scores.get('pricey-fast')!.price).toBe(1);
    expect(sortResults(results, 'recommended')[0].id).toBe('mid-direct');
  });
  it('does not mutate the input and is deterministic', () => {
    const copy = [...results];
    sortResults(results, 'cheapest');
    expect(results).toEqual(copy);
    expect(sortResults(results, 'recommended')).toEqual(sortResults([...results].reverse(), 'recommended'));
  });
});

describe('filters', () => {
  it('filters by outbound departure and arrival time of day (airport-local)', () => {
    const at = (dep: string, arr: string) => ({ ...leg(0, 120), departing_at: '2026-12-10T' + dep + ':00+05:00', arriving_at: '2026-12-10T' + arr + ':00+04:00' });
    const list = [flight('early', 100, { legs: [at('05:30', '07:00')] }), flight('evening', 100, { legs: [at('19:15', '21:00')] })];
    expect(applyFilters(list, { ...emptyFilters, departs: ['night'] }).map((r) => r.id)).toEqual(['early']);
    expect(applyFilters(list, { ...emptyFilters, arrives: ['evening'] }).map((r) => r.id)).toEqual(['evening']);
    expect(facets(list).departs).toEqual({ night: 1, morning: 0, afternoon: 0, evening: 1 });
  });

  it('filters by stops using the journey with most stops', () => {
    expect(applyFilters(results, { ...emptyFilters, stops: ['direct'] }).map((r) => r.id)).toEqual(['mid-direct', 'pricey-fast']);
    expect(applyFilters(results, { ...emptyFilters, stops: ['two'] }).map((r) => r.id)).toEqual(['two-stops']);
  });
  it('filters by airline, price, duration, baggage and refundability', () => {
    expect(applyFilters(results, { ...emptyFilters, airlines: ['Air B'] })).toHaveLength(2);
    expect(applyFilters(results, { ...emptyFilters, maxPrice: 150 }).map((r) => r.id)).toEqual(['cheap-slow', 'mid-direct', 'two-stops']);
    expect(applyFilters(results, { ...emptyFilters, maxDuration: 300 }).map((r) => r.id)).toEqual(['mid-direct', 'pricey-fast']);
    expect(applyFilters(results, { ...emptyFilters, checked: true, carryOn: true }).map((r) => r.id)).toEqual(['mid-direct']);
    // Unknown refundability (null) is never treated as refundable.
    expect(applyFilters(results, { ...emptyFilters, refundableOnly: true }).map((r) => r.id)).toEqual(['mid-direct']);
  });
  it('counts active filters and clearing restores all results', () => {
    const f = { ...emptyFilters, stops: ['direct' as const], maxPrice: 100, refundableOnly: true };
    expect(activeFilterCount(f)).toBe(3);
    expect(applyFilters(results, emptyFilters)).toHaveLength(results.length);
  });
});

describe('facets', () => {
  it('derives counts and bounds from the actual results', () => {
    const f = facets(results);
    expect(f.stops).toEqual({ direct: 2, one: 1, two: 1 });
    expect(f.airlines).toEqual([['Air A', 2], ['Air B', 2]]);
    expect([f.priceMin, f.priceMax]).toEqual([100, 400]);
    expect(f.refundableKnown).toBe(true);
    expect(f.refundableCount).toBe(1);
    expect(f.currencies).toEqual(['USD']);
  });
  it('handles empty results', () => {
    expect(facets([]).priceMax).toBe(0);
    expect(scoreResults([]).size).toBe(0);
  });
});
