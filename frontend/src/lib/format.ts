import type { Airport, AirportRef, Baggage, Flight, Itinerary } from './types';

export const airports: Record<string, string> = {
  KHI: 'Karachi', LHE: 'Lahore', ISB: 'Islamabad', DXB: 'Dubai', AUH: 'Abu Dhabi', SHJ: 'Sharjah', DOH: 'Doha', BAH: 'Bahrain',
  MCT: 'Muscat', JED: 'Jeddah', RUH: 'Riyadh', IST: 'Istanbul', SAW: 'Istanbul', LHR: 'London', LGW: 'London', SIN: 'Singapore',
  KUL: 'Kuala Lumpur', BKK: 'Bangkok', JFK: 'New York', CDG: 'Paris', MAN: 'Manchester', FRA: 'Frankfurt', AMS: 'Amsterdam',
  KWI: 'Kuwait City', CAI: 'Cairo', DEL: 'Delhi', BOM: 'Mumbai', TYO: 'Tokyo', NRT: 'Tokyo', HND: 'Tokyo', YYZ: 'Toronto',
};
// Airports returned by the API are remembered so any code can be shown with its city.
const known = new Map<string, AirportRef>();
export const rememberAirports = (list: (Airport | AirportRef)[]) => list.forEach((a) => known.set(a.code, toRef(a)));
export const knownAirport = (code: string) => known.get(code);
export const cityOf = (code: string) => known.get(code)?.city ?? airports[code] ?? code;
export const toRef = (a: Airport | AirportRef): AirportRef => ({ code: a.code, name: a.name, city: a.city, country: a.country, country_code: a.country_code, lat: a.lat, lon: a.lon });
/** "Karachi, Pakistan · KHI" */
export const airportText = (a: AirportRef) => `${a.city}, ${a.country} · ${a.code}`;
export const airportLabel = (code: string, city?: string) => `${city || cityOf(code)} (${code})`;
/** Extract an IATA code from "KHI" or "Karachi (KHI)"; null for free text. */
export const codeOf = (s: string): string | null => {
  const t = s.trim();
  if (/^[A-Za-z]{3}$/.test(t)) return t.toUpperCase();
  return t.match(/\(([A-Za-z]{3})\)\s*$/)?.[1]?.toUpperCase() ?? null;
};

export const money = (value: number, currency = 'USD', digits = 0) => {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, currencyDisplay: 'code', maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value).replace(/ /g, ' ');
  } catch { return `${currency} ${value.toFixed(digits)}`; }
};
const toDate = (value: string) => new Date(`${value.slice(0, 10)}T12:00:00`);
export const shortDate = (value: string) => value ? toDate(value).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) : '';
export const dayMonth = (value: string) => value ? toDate(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '';
export const fullDate = (value: string) => value ? toDate(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
export const dateTime = (value: string) => new Date(value).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
/** Clock time as written in the ISO string, so airport-local times are not shifted by the browser's timezone. */
export const timeOf = (value?: string) => value?.match(/T?(\d{2}:\d{2})/)?.[1] ?? '--:--';
export const dayOffset = (from: string, to: string) => Math.round((toDate(to).getTime() - toDate(from).getTime()) / 86400000);
export const durationLabel = (minutes?: number | null) => {
  if (minutes == null) return 'Not provided';
  const h = Math.floor(minutes / 60), m = minutes % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
};
export const todayIso = () => new Date().toISOString().slice(0, 10);
export const addDaysIso = (days: number, from = new Date()) => { const d = new Date(from); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); };

export const legsOf = (f: Flight): Itinerary[] => f.itineraries?.length ? f.itineraries : [{
  origin: f.origin, destination: f.destination, departing_at: `${f.departure_date}T${f.departure_time}`,
  arriving_at: `${f.departure_date}T${f.arrival_time}`, duration_minutes: f.duration_minutes, stops: f.stops, segments: [],
}];
export const stopsLabel = (n: number) => n === 0 ? 'Direct' : `${n} stop${n > 1 ? 's' : ''}`;
export const statusLabel = (s: string) => s === 'live' ? 'Live fare' : s === 'test' ? 'Test fare' : 'Demo fare';

/** Minutes between two ISO datetimes with offsets (true elapsed time, timezone-safe). */
export const minutesBetween = (a: string, b: string) => Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000);

export const bagOf = (f: Flight, type: string): Baggage | undefined => f.baggage_allowances?.find((b) => b.baggage_type === type);
export const bagText = (b?: Baggage) => {
  if (!b) return 'Not supplied';
  if (b.quantity === 0) return 'Not included';
  if (b.quantity != null) return b.weight ? `${b.quantity} × ${b.weight} ${b.weight_unit ?? 'kg'}` : `${b.quantity} ${b.quantity === 1 ? 'bag' : 'bags'}`;
  if (b.weight != null) return `${b.weight} ${b.weight_unit ?? 'kg'}`;
  return 'Included';
};

/** "just now", "35 minutes ago", "2 hours ago", "yesterday", "3 days ago", then a date. Future times read "in …". */
export function relativeTime(value: string | Date, now: Date = new Date()): string {
  const then = typeof value === 'string' ? new Date(value) : value;
  const diff = now.getTime() - then.getTime();
  if (Number.isNaN(diff)) return '';
  const future = diff < 0;
  const mins = Math.round(Math.abs(diff) / 60000);
  const say = (n: number, unit: string) => (future ? `in ${n} ${unit}${n === 1 ? '' : 's'}` : `${n} ${unit}${n === 1 ? '' : 's'} ago`);
  if (mins < 1) return future ? 'in under a minute' : 'just now';
  if (mins < 60) return say(mins, 'minute');
  const hours = Math.round(mins / 60);
  if (hours < 24) return say(hours, 'hour');
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round(Math.abs(startOfDay(now) - startOfDay(then)) / 86400000);
  if (days === 1) return future ? 'tomorrow' : 'yesterday';
  if (days < 7) return say(days, 'day');
  return then.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: then.getFullYear() === now.getFullYear() ? undefined : 'numeric' });
}
