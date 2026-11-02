// Date helpers for the calendar. All dates are ISO "YYYY-MM-DD" strings in local time.

export const pad = (n: number) => String(n).padStart(2, '0');
export const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parseIso = (s: string) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
export const addDays = (s: string, n: number) => { const d = parseIso(s); d.setDate(d.getDate() + n); return iso(d); };
export const addMonths = (year: number, month: number, n: number) => { const d = new Date(year, month + n, 1); return { year: d.getFullYear(), month: d.getMonth() }; };

/** Weeks (Monday first) for a month; days outside the month are null. */
export function monthGrid(year: number, month: number): (string | null)[][] {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (string | null)[] = Array(offset).fill(null);
  for (let d = 1; d <= days; d++) cells.push(iso(new Date(year, month, d)));
  while (cells.length % 7) cells.push(null);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

export const inRange = (day: string, start: string, end: string) => !!start && !!end && day > start && day < end;

/** Whole nights between two ISO dates (0 when either is missing or out of order). */
export const nightsBetween = (from: string, to: string) =>
  from && to && to > from ? Math.round((parseIso(to).getTime() - parseIso(from).getTime()) / 86400000) : 0;

type Priced = { lowest_price: number };
/** The cheapest observed date in [from, to] (inclusive), earliest on ties; null when none has data. */
export function cheapestIn<T extends Priced>(days: Record<string, T> | undefined, from: string, to: string): { date: string; info: T } | null {
  let best: { date: string; info: T } | null = null;
  for (const [date, info] of Object.entries(days ?? {})) {
    if (date < from || date > to) continue;
    if (!best || info.lowest_price < best.info.lowest_price || (info.lowest_price === best.info.lowest_price && date < best.date)) best = { date, info };
  }
  return best;
}

/** First and last ISO day of a month. */
export const monthBounds = (year: number, month: number) => ({ first: iso(new Date(year, month, 1)), last: iso(new Date(year, month + 1, 0)) });

/** Short price for a calendar cell: 1 234 → "1,234", 12 500 → "12.5k". */
export const compactPrice = (v: number) => (v >= 10000 ? `${(v / 1000).toFixed(v >= 100000 ? 0 : 1)}k` : Math.round(v).toLocaleString('en-US'));
