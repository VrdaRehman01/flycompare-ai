import { api } from './api';
import { addDaysIso, rememberAirports, toRef } from './format';
import { readSession, writeSession } from './router';
import type { Airport, AirportRef, DataStatus } from './types';

/* ------------------------------------------------------------------ types */

export type CitySummary = {
  key: string; city: string; country: string; country_code: string; region: string; lat: number; lon: number;
  airport: string; airports: { code: string; name: string }[];
};
type Provided = { data_status: DataStatus; provider: string; notice: string | null; city: CitySummary };

export type PropertyType = 'hotel' | 'apartment' | 'resort' | 'hostel' | 'villa';
export type Stay = {
  id: string; name: string; property_type: PropertyType; stars: number | null; review_score: number | null; review_count: number | null;
  area: string; area_best_for: string | null; address: string; lat: number | null; lon: number | null; distance_km: number | null;
  photo_url: string | null; amenities: string[]; free_cancellation: boolean | null; breakfast_included: boolean | null;
  nightly_price: number; total_price: number; currency: string; rooms_left: number | null; sleeps: number | null;
};
export type StaysResponse = Provided & { check_in: string; check_out: string; nights: number; adults: number; children: number; rooms: number; results: Stay[] };

export type CarOffer = {
  id: string; category: string; model: string; supplier: string; supplier_rating: number; seats: number; bags_large: number; bags_small: number;
  doors: number; transmission: 'Automatic' | 'Manual'; air_conditioning: boolean; fuel_policy: string; mileage: string; pickup: string; in_terminal: boolean;
  free_cancellation: boolean; includes: string[]; deposit: number; price_per_day: number; driver_fees: number; total_price: number; currency: string;
};
export type CarsResponse = Provided & { airport: Airport; rental_days: number; notes: string[]; results: CarOffer[] };

export type TransferOffer = {
  id: string; kind: 'shared' | 'private'; vehicle: string; supplier: string; max_passengers: number | null; max_bags: number; distance_km: number;
  duration_minutes: number; meet_and_greet: boolean; flight_tracking: boolean; free_waiting_minutes: number; free_cancellation: string;
  price_basis: 'per person' | 'per vehicle'; unit_price: number; total_price: number; currency: string;
};
export type TransfersResponse = Provided & { airport: Airport; distance_km: number; estimated_minutes: number; peak_traffic: boolean; direction: 'from_airport' | 'to_airport'; passengers: number; bags: number; results: TransferOffer[] };

export type Tour = {
  id: string; kind: 'group' | 'private'; title: string; summary: string; operator: string;
  stops: { name: string; category: string; hours: number; blurb: string }[]; categories: string[]; duration_hours: number; languages: string[];
  rating: number; reviews: number; includes: string[]; excludes: string[]; admission_included_usd: number; free_cancellation: string;
  currency: string; price_basis: 'per person' | 'per party'; price_per_person: number; total_price: number;
  group_size_max?: number; start_times: string[]; pickup: string; spots_left?: number | null; vehicle?: string; customisable?: boolean;
};
export type ToursResponse = Provided & { kind: 'group' | 'private'; date: string; travellers: number; results: Tour[] };

export type GuideCard = CitySummary & { tagline: string; top_categories: string[]; sights: number };
export type ClimateMonth = { month: number; name: string; avg_high_c: number; avg_low_c: number | null; precip_mm: number; rainy_days: number; score: number };
export type Guide = CitySummary & {
  curated: boolean; tagline: string | null; language: string | null; currency: string | null; typical_hotel_night_usd: number;
  areas: { name: string; blurb: string; best_for: string }[];
  sights: { name: string; category: string; hours: number; usd: number; slot: string; blurb: string }[];
  tips: string[]; content_note: string;
  overview: { title: string; extract: string; url: string | null; source: string } | null;
  climate: { year: number; months: ClimateMonth[]; best_months: string[]; avoid_months: string[]; source: string } | null;
};

export type PlanItem = { time: string; kind: 'sight' | 'meal' | 'free' | 'travel'; title: string; detail: string; category?: string; hours?: number; usd?: number };
export type ForecastDay = { date: string; condition: string; icon: string; max_c: number | null; min_c: number | null; precipitation_probability: number | null };
export type Plan = {
  city: CitySummary; curated: boolean; start: string; end: string; nights: number; travellers: number;
  pace: Pace; budget: Budget; interests: string[];
  days: { date: string; kind: 'arrival' | 'full' | 'departure'; title: string; area: string; items: PlanItem[]; activities_usd: number }[];
  costs: { currency: string; lines: { label: string; amount: number }[]; total: number; excludes: string; basis: string };
  weather: { kind: 'forecast'; source: string; days: ForecastDay[] } | { kind: 'climate'; source: string; months: ClimateMonth[] } | null;
  tips: string[]; note: string | null;
};
export type Pace = 'relaxed' | 'balanced' | 'packed';
export type Budget = 'budget' | 'mid' | 'luxury';

export const INTERESTS = ['Culture', 'Nature', 'Beach', 'Family', 'City', 'Food', 'Shopping', 'Adventure'] as const;

/* ------------------------------------------------- shared trip in progress */

/**
 * The trip being planned is shared across Stays, Cars, Tours, Planner and
 * Flight & Hotel for this browser tab, so dates and travellers carry over.
 */
export type Trip = { destination: AirportRef | null; start: string; end: string; adults: number; children: number; rooms: number };
const TRIP_KEY = 'fc-trip';

export function defaultTrip(): Trip {
  return { destination: null, start: addDaysIso(14), end: addDaysIso(18), adults: 2, children: 0, rooms: 1 };
}

export function readTrip(): Trip {
  const saved = readSession<Trip>(TRIP_KEY);
  const base = defaultTrip();
  if (!saved || saved.start < addDaysIso(0)) return { ...base, destination: saved?.destination ?? null };
  return { ...base, ...saved };
}

export function writeTrip(trip: Trip) {
  writeSession(TRIP_KEY, trip);
}

/** Resolve a route location (airport code) to an airport for the location field. */
export async function lookupLocation(location: string | undefined): Promise<AirportRef | null> {
  const code = location?.includes('|') ? null : location?.toUpperCase();
  if (!code || !/^[A-Z]{3}$/.test(code)) return null;
  const list = await api<Airport[]>(`/api/airports/lookup?codes=${code}`);
  rememberAirports(list);
  return list[0] ? toRef(list[0]) : null;
}

export const nightsBetween = (a: string, b: string) => Math.max(0, Math.round((new Date(`${b}T12:00:00`).getTime() - new Date(`${a}T12:00:00`).getTime()) / 86400000));

export const reviewLabel = (score: number) => score >= 9 ? 'Exceptional' : score >= 8.5 ? 'Excellent' : score >= 8 ? 'Very good' : score >= 7 ? 'Good' : 'Pleasant';

export const PROPERTY_LABEL: Record<PropertyType, string> = { hotel: 'Hotel', apartment: 'Apartment', resort: 'Resort', hostel: 'Hostel', villa: 'Villa' };
