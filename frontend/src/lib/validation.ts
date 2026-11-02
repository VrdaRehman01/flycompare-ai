import { todayIso } from './format';
import type { AirportRef, Passengers, SearchForm } from './types';

export const MAX_SEATS = 9; // Duffel: at most 9 seated passengers (adults + children)
export const MAX_LEGS = 4;

export type FieldErrors = Partial<Record<string, string>>;

/** Mirrors the backend rules so problems are explained before a request is sent. */
export function passengerErrors(p: Passengers): string | null {
  if (p.adults < 1) return 'At least one adult is required.';
  if (p.childAges.some((a) => a < 2 || a > 17)) return 'Each child must be aged 2 to 17.';
  if (p.adults + p.childAges.length > MAX_SEATS) return `At most ${MAX_SEATS} passengers with seats (adults + children).`;
  if (p.infants > p.adults) return 'Each infant travels on an adult’s lap, so infants cannot outnumber adults.';
  return null;
}

export const passengerSummary = (p: Passengers) => {
  const parts = [`${p.adults} ${p.adults === 1 ? 'adult' : 'adults'}`];
  const c = p.childAges.length;
  if (c) parts.push(`${c} ${c === 1 ? 'child' : 'children'}`);
  if (p.infants) parts.push(`${p.infants} ${p.infants === 1 ? 'infant' : 'infants'}`);
  return parts.join(', ');
};
export const travellerCount = (p: Passengers) => p.adults + p.childAges.length + p.infants;

export function validateSearch(f: SearchForm): FieldErrors {
  const errors: FieldErrors = {};
  const today = todayIso();
  const pax = passengerErrors(f.passengers);
  if (pax) errors.passengers = pax;
  if (f.tripType === 'multi-city') {
    if (f.legs.length < 2) errors.legs = 'Add at least two flights.';
    f.legs.forEach((leg, i) => {
      if (!leg.origin) errors[`leg${i}.origin`] = 'Choose an airport.';
      if (!leg.destination) errors[`leg${i}.destination`] = 'Choose an airport.';
      if (leg.origin && leg.destination && leg.origin.code === leg.destination.code) errors[`leg${i}.destination`] = 'Choose a different airport.';
      if (!leg.date) errors[`leg${i}.date`] = 'Select a date.';
      else if (leg.date < today) errors[`leg${i}.date`] = 'Date cannot be in the past.';
      else if (i && f.legs[i - 1].date && leg.date < f.legs[i - 1].date) errors[`leg${i}.date`] = 'Must be on or after the previous flight.';
    });
    return errors;
  }
  if (!f.origin) errors.origin = 'Choose a departure airport.';
  if (!f.destination) errors.destination = 'Choose a destination airport.';
  if (f.origin && f.destination && f.origin.code === f.destination.code) errors.destination = 'Choose a different airport from the origin.';
  if (!f.departure) errors.departure = 'Select a departure date.';
  else if (f.departure < today) errors.departure = 'Departure cannot be in the past.';
  if (f.tripType === 'round-trip') {
    if (!f.returnDate) errors.returnDate = 'Select a return date.';
    else if (f.departure && f.returnDate < f.departure) errors.returnDate = 'Return must be on or after departure.';
  }
  return errors;
}

/** Request body for POST /api/flights/search. Only verified airport codes are sent. */
export function searchBody(f: SearchForm) {
  const pax = { passengers: f.passengers.adults, child_ages: f.passengers.childAges, infants: f.passengers.infants, cabin: f.cabin };
  if (f.tripType === 'multi-city') {
    const legs = f.legs.map((l) => ({ origin: l.origin!.code, destination: l.destination!.code, departure_date: l.date }));
    return { origin: legs[0].origin, destination: legs[legs.length - 1].destination, departure_date: legs[0].departure_date, return_date: null, trip_type: 'multi-city', legs, ...pax };
  }
  return {
    origin: f.origin!.code, destination: f.destination!.code, departure_date: f.departure,
    return_date: f.tripType === 'round-trip' ? f.returnDate : null, trip_type: f.tripType, ...pax,
  };
}

export const emptyForm = (origin: AirportRef | null = null): SearchForm => ({
  tripType: 'round-trip', origin, destination: null, departure: '', returnDate: '', cabin: 'Economy',
  passengers: { adults: 1, childAges: [], infants: 0 }, legs: [{ origin, destination: null, date: '' }, { origin: null, destination: null, date: '' }],
});

/** Session data saved by older versions stored airports as plain strings; ignore it. */
export function isCurrentForm(value: unknown): value is SearchForm {
  const f = value as SearchForm | null;
  return !!f && typeof f === 'object' && typeof f.passengers === 'object' && Array.isArray(f.passengers?.childAges) && Array.isArray(f.legs) && (f.origin === null || typeof f.origin === 'object');
}
