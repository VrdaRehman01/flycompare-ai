import { describe, expect, it } from 'vitest';
import { convert } from './currency';
import { codeOf, minutesBetween, timeOf } from './format';
import { hrefFor, parseHash } from './router';
import { readThemePreference, resolveTheme, THEME_KEY, writeThemePreference } from './theme';
import type { Rates } from './types';

class MemoryStorage {
  data = new Map<string, string>();
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
}

describe('theme persistence', () => {
  it('defaults to system and persists the chosen preference', () => {
    const storage = new MemoryStorage();
    expect(readThemePreference(storage)).toBe('system');
    writeThemePreference(storage, 'dark');
    expect(storage.getItem(THEME_KEY)).toBe('dark');
    expect(readThemePreference(storage)).toBe('dark');
  });
  it('ignores invalid stored values and blocked storage', () => {
    const storage = new MemoryStorage();
    storage.setItem(THEME_KEY, 'purple');
    expect(readThemePreference(storage)).toBe('system');
    const blocked = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
    expect(readThemePreference(blocked)).toBe('system');
    expect(() => writeThemePreference(blocked, 'light')).not.toThrow();
  });
  it('resolves system preference from the OS setting', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
  });
});

describe('currency conversion', () => {
  const rates: Rates = { base: 'USD', date: '2026-10-30', source: 'ECB', rates: { EUR: 0.9 } };
  it('converts only with a matching base rate', () => {
    expect(convert(100, 'USD', 'EUR', rates)).toBeCloseTo(90);
    expect(convert(100, 'USD', 'USD', null)).toBe(100);
    expect(convert(100, 'USD', 'PKR', rates)).toBeNull(); // no rate -> show original
    expect(convert(100, 'GBP', 'EUR', rates)).toBeNull(); // wrong base -> never guess
    expect(convert(100, 'USD', 'EUR', null)).toBeNull();
  });
});

describe('formatting', () => {
  it('reads airport-local clock time without timezone shifts', () => {
    expect(timeOf('2026-12-10T23:45:00+05:00')).toBe('23:45');
  });
  it('computes true elapsed minutes across timezones for layovers', () => {
    expect(minutesBetween('2026-11-15T05:00:00+03:00', '2026-11-15T08:00:00+03:00')).toBe(180);
    expect(minutesBetween('2026-11-15T12:00:00+04:00', '2026-11-15T12:00:00+05:00')).toBe(-60);
  });
  it('extracts airport codes', () => {
    expect(codeOf('Karachi (KHI)')).toBe('KHI');
    expect(codeOf('dxb')).toBe('DXB');
    expect(codeOf('Japan')).toBeNull();
  });
});

describe('routing', () => {
  it('round-trips routes through the URL hash', () => {
    expect(parseHash('#/insights')).toEqual({ page: 'insights' });
    expect(parseHash('#/account/saved')).toEqual({ page: 'account', tab: 'saved' });
    expect(parseHash('#/account/unknown')).toEqual({ page: 'account', tab: 'profile' });
    expect(parseHash('')).toEqual({ page: 'home' });
    expect(hrefFor({ page: 'details' })).toBe('#/flight');
  });
});

describe('relativeTime', () => {
  const now = new Date('2026-10-31T15:00:00');
  it('describes recent and older times from real timestamps', async () => {
    const { relativeTime } = await import('./format');
    expect(relativeTime(new Date('2026-10-31T14:59:40'), now)).toBe('just now');
    expect(relativeTime(new Date('2026-10-31T14:25:00'), now)).toBe('35 minutes ago');
    expect(relativeTime(new Date('2026-10-31T13:00:00'), now)).toBe('2 hours ago');
    expect(relativeTime(new Date('2026-10-30T09:00:00'), now)).toBe('yesterday');
    expect(relativeTime(new Date('2026-10-28T09:00:00'), now)).toBe('3 days ago');
    expect(relativeTime(new Date('2026-10-31T15:20:00'), now)).toBe('in 20 minutes');
    expect(relativeTime('not a date', now)).toBe('');
  });
});

describe('public route day labels', () => {
  it('shows only day-level timing', async () => {
    const { dayAgo } = await import('../components/PopularRoutes');
    const now = new Date('2026-11-02T09:00:00');
    expect(dayAgo('2026-11-02', now)).toBe('today');
    expect(dayAgo('2026-11-01', now)).toBe('yesterday');
    expect(dayAgo('2026-10-29', now)).toBe('4 days ago');
    expect(dayAgo('2026-10-20', now)).toBe('20 Oct');
  });
});
