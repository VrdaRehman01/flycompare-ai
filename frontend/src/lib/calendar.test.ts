import { describe, expect, it } from 'vitest';
import { addDays, cheapestIn, compactPrice, monthBounds, monthGrid, nightsBetween } from './calendar';

describe('calendar helpers', () => {
  it('counts nights and ignores reversed or missing dates', () => {
    expect(nightsBetween('2026-11-10', '2026-11-17')).toBe(7);
    expect(nightsBetween('2026-11-17', '2026-11-10')).toBe(0);
    expect(nightsBetween('', '2026-11-10')).toBe(0);
    expect(nightsBetween('2027-03-27', '2027-03-29')).toBe(2); // across a DST change
  });
  it('finds the cheapest observed date in a window, earliest on ties', () => {
    const days = { '2026-11-09': { lowest_price: 90 }, '2026-11-11': { lowest_price: 120 }, '2026-11-12': { lowest_price: 100 }, '2026-11-14': { lowest_price: 100 } };
    expect(cheapestIn(days, '2026-11-10', '2026-11-16')?.date).toBe('2026-11-12');
    expect(cheapestIn(days, '2026-11-15', '2026-11-20')).toBeNull();
    expect(cheapestIn(undefined, '2026-11-01', '2026-11-30')).toBeNull();
  });
  it('builds Monday-first month grids and bounds', () => {
    const weeks = monthGrid(2026, 10); // November 2026 starts on a Sunday
    expect(weeks[0].slice(0, 6).every((d) => d === null)).toBe(true);
    expect(weeks[0][6]).toBe('2026-11-01');
    expect(monthBounds(2027, 1)).toEqual({ first: '2027-02-01', last: '2027-02-28' });
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
  });
  it('formats compact prices', () => {
    expect(compactPrice(112.4)).toBe('112');
    expect(compactPrice(1234)).toBe('1,234');
    expect(compactPrice(12500)).toBe('12.5k');
    expect(compactPrice(245000)).toBe('245k');
  });
});
