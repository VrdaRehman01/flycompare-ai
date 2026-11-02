import { describe, expect, it } from 'vitest';
import { addDays, inRange, monthGrid } from './calendar';
import { confidentNearest, fixAntimeridian, greatCircle, readGeoState, readSavedOrigin, roundCoord, saveOrigin, writeGeoState } from './geo';
import type { AirportRef, SearchForm } from './types';
import { emptyForm, isCurrentForm, passengerErrors, passengerSummary, searchBody, validateSearch } from './validation';

class MemoryStorage {
  data = new Map<string, string>();
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
  removeItem(k: string) { this.data.delete(k); }
}

const KHI: AirportRef = { code: 'KHI', name: 'Jinnah International Airport', city: 'Karachi', country: 'Pakistan', lat: 24.9, lon: 67.16 };
const DXB: AirportRef = { code: 'DXB', name: 'Dubai International Airport', city: 'Dubai', country: 'United Arab Emirates', lat: 25.25, lon: 55.36 };
const IST: AirportRef = { code: 'IST', name: 'Istanbul Airport', city: 'Istanbul', country: 'Türkiye', lat: 41.26, lon: 28.74 };
const base: SearchForm = { ...emptyForm(KHI), destination: DXB, departure: '2999-01-10', returnDate: '2999-01-17' };

describe('search validation', () => {
  it('accepts a valid round trip and builds a code-only request', () => {
    expect(validateSearch(base)).toEqual({});
    expect(searchBody(base)).toEqual({ origin: 'KHI', destination: 'DXB', departure_date: '2999-01-10', return_date: '2999-01-17', trip_type: 'round-trip', passengers: 1, child_ages: [], infants: 0, cabin: 'Economy' });
  });
  it('requires verified airports and valid dates', () => {
    expect(validateSearch({ ...base, destination: null }).destination).toBeTruthy();
    expect(validateSearch({ ...base, destination: KHI }).destination).toMatch(/different/);
    expect(validateSearch({ ...base, departure: '2000-01-01' }).departure).toMatch(/past/);
    expect(validateSearch({ ...base, returnDate: '2999-01-01' }).returnDate).toMatch(/after/);
    expect(validateSearch({ ...base, returnDate: '' }).returnDate).toBeTruthy();
    expect(validateSearch({ ...base, tripType: 'one-way', returnDate: '' })).toEqual({});
    expect(searchBody({ ...base, tripType: 'one-way' }).return_date).toBeNull();
  });
  it('validates and serialises multi-city trips', () => {
    const multi: SearchForm = { ...base, tripType: 'multi-city', legs: [{ origin: KHI, destination: DXB, date: '2999-01-10' }, { origin: DXB, destination: IST, date: '2999-01-15' }] };
    expect(validateSearch(multi)).toEqual({});
    const body = searchBody(multi);
    expect(body).toMatchObject({ trip_type: 'multi-city', origin: 'KHI', destination: 'IST', departure_date: '2999-01-10' });
    expect((body as { legs: unknown[] }).legs).toEqual([{ origin: 'KHI', destination: 'DXB', departure_date: '2999-01-10' }, { origin: 'DXB', destination: 'IST', departure_date: '2999-01-15' }]);
    const backwards = { ...multi, legs: [multi.legs[0], { ...multi.legs[1], date: '2999-01-05' }] };
    expect(validateSearch(backwards)['leg1.date']).toMatch(/previous/);
    expect(validateSearch({ ...multi, legs: [multi.legs[0], { origin: DXB, destination: null, date: '' }] })['leg1.destination']).toBeTruthy();
  });
  it('ignores search state saved by the old string-based form', () => {
    expect(isCurrentForm(base)).toBe(true);
    expect(isCurrentForm({ origin: 'Karachi (KHI)', passengers: 1 })).toBe(false);
  });
});

describe('passengers', () => {
  it('applies seat, age and lap-infant rules', () => {
    expect(passengerErrors({ adults: 2, childAges: [5, 12], infants: 2 })).toBeNull();
    expect(passengerErrors({ adults: 1, childAges: [], infants: 2 })).toMatch(/infants/);
    expect(passengerErrors({ adults: 5, childAges: [3, 4, 5, 6, 7], infants: 0 })).toMatch(/9/);
    expect(passengerErrors({ adults: 1, childAges: [1], infants: 0 })).toMatch(/2 to 17/);
    expect(passengerErrors({ adults: 0, childAges: [], infants: 0 })).toMatch(/adult/);
  });
  it('summarises passenger counts', () => {
    expect(passengerSummary({ adults: 2, childAges: [7], infants: 1 })).toBe('2 adults, 1 child, 1 infant');
    expect(passengerSummary({ adults: 1, childAges: [], infants: 0 })).toBe('1 adult');
  });
  it('sends child ages to the API', () => {
    expect(searchBody({ ...base, passengers: { adults: 2, childAges: [4, 15], infants: 1 } })).toMatchObject({ passengers: 2, child_ages: [4, 15], infants: 1 });
  });
});

describe('current location', () => {
  it('rounds coordinates before sending them', () => {
    expect(roundCoord(24.860734)).toBe(24.86);
    expect(roundCoord(-67.00114)).toBe(-67);
  });
  it('only auto-selects an airport that is confidently close', () => {
    expect(confidentNearest([{ code: 'KHI', distance_km: 17 }])?.code).toBe('KHI');
    expect(confidentNearest([{ code: 'XXX', distance_km: 240 }])).toBeNull();
    expect(confidentNearest([])).toBeNull();
  });
  it('remembers the chosen airport and the permission outcome, never coordinates', () => {
    const storage = new MemoryStorage();
    expect(readSavedOrigin(storage)).toBeNull();
    saveOrigin(storage, KHI);
    expect(readSavedOrigin(storage)?.code).toBe('KHI');
    expect(readGeoState(storage)).toBe('unasked');
    writeGeoState(storage, 'denied');
    expect(readGeoState(storage)).toBe('denied');
    saveOrigin(storage, null);
    expect(readSavedOrigin(storage)).toBeNull();
    storage.setItem('fc-origin', '{"code":"karachi"}');
    expect(readSavedOrigin(storage)).toBeNull();
  });
});

describe('map routes', () => {
  it('draws great-circle paths between airports', () => {
    const path = greatCircle([67.16, 24.9], [-0.46, 51.47], 32);
    expect(path).toHaveLength(33);
    expect(path[0][0]).toBeCloseTo(67.16, 4);
    expect(path[32][1]).toBeCloseTo(51.47, 4);
    // A great-circle path bows towards the pole compared with a straight line on the map.
    expect(path[16][1]).toBeGreaterThan((24.9 + 51.47) / 2);
  });
  it('keeps routes across the antimeridian continuous', () => {
    const path = greatCircle([139.78, 35.55], [-122.38, 37.62], 20); // Tokyo → San Francisco
    for (let i = 1; i < path.length; i++) expect(Math.abs(path[i][0] - path[i - 1][0])).toBeLessThan(30);
  });
});

describe('map basemap', () => {
  it('repairs rings that cross the antimeridian and drops Antarctica', () => {
    const fc: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [
      { type: 'Feature', id: '242', properties: {}, geometry: { type: 'Polygon', coordinates: [[[179, -16], [-179, -16], [-179, -18], [179, -18], [179, -16]]] } },
      { type: 'Feature', id: '010', properties: {}, geometry: { type: 'Polygon', coordinates: [[[0, -80], [10, -80], [10, -85], [0, -80]]] } },
      { type: 'Feature', id: '586', properties: {}, geometry: { type: 'Polygon', coordinates: [[[61, 24], [75, 24], [75, 37], [61, 24]]] } },
    ] };
    const fixed = fixAntimeridian(fc);
    expect(fixed.features.map((f) => f.id)).toEqual(['242', '586']);
    const fiji = fixed.features[0].geometry as GeoJSON.MultiPolygon;
    expect(fiji.coordinates).toHaveLength(2); // one copy each side of the map
    for (const poly of fiji.coordinates) {
      const ring = poly[0];
      for (let i = 1; i < ring.length; i++) expect(Math.abs(ring[i][0] - ring[i - 1][0])).toBeLessThan(180);
    }
    expect((fixed.features[1].geometry as GeoJSON.MultiPolygon).coordinates).toHaveLength(1);
  });
});

describe('calendar', () => {
  it('builds Monday-first month grids', () => {
    const weeks = monthGrid(2026, 10); // November 2026 starts on a Sunday
    expect(weeks[0].slice(0, 6).every((d) => d === null)).toBe(true);
    expect(weeks[0][6]).toBe('2026-11-01');
    expect(weeks.flat().filter(Boolean)).toHaveLength(30);
  });
  it('adds days across month ends and detects ranges', () => {
    expect(addDays('2026-11-28', 7)).toBe('2026-12-05');
    expect(inRange('2026-11-15', '2026-11-10', '2026-11-20')).toBe(true);
    expect(inRange('2026-11-10', '2026-11-10', '2026-11-20')).toBe(false);
  });
});
