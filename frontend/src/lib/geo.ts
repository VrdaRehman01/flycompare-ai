import type { AirportRef } from './types';

/** Round coordinates to 2 decimals (~1 km) before sending them anywhere. */
export const roundCoord = (value: number) => Math.round(value * 100) / 100;

const toRad = (d: number) => (d * Math.PI) / 180;
const toDeg = (r: number) => (r * 180) / Math.PI;

export function distanceKm(a: [number, number], b: [number, number]) {
  const [lon1, lat1] = a.map(toRad), [lon2, lat2] = b.map(toRad);
  const h = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

/**
 * Points along the great-circle path between two [lon, lat] positions. On a
 * flat map this produces the familiar curved flight path. Longitudes are
 * unwrapped so routes crossing the antimeridian draw continuously.
 */
export function greatCircle(a: [number, number], b: [number, number], steps = 64): [number, number][] {
  const [lon1, lat1] = a.map(toRad), [lon2, lat2] = b.map(toRad);
  const d = 2 * Math.asin(Math.sqrt(Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2));
  if (d === 0) return [a, b];
  const points: [number, number][] = [];
  let prevLon: number | null = null;
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d), B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
    const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    let lon = toDeg(Math.atan2(y, x));
    const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
    if (prevLon !== null) {
      while (lon - prevLon > 180) lon -= 360;
      while (lon - prevLon < -180) lon += 360;
    }
    prevLon = lon;
    points.push([lon, lat]);
  }
  return points;
}

/**
 * Natural Earth rings that cross the antimeridian (e.g. Chukotka, Fiji) are
 * stored with longitudes jumping between +180 and -180. Drawn as-is they fill
 * a band across the whole map, so each such ring is shifted into one
 * continuous range and duplicated on the other side of the map.
 */
export function fixAntimeridian(fc: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
  const fixRing = (ring: GeoJSON.Position[]): GeoJSON.Position[][] => {
    const crosses = ring.some((p, i) => i > 0 && Math.abs(p[0] - ring[i - 1][0]) > 180);
    if (!crosses) return [ring];
    const east = ring.map(([x, y]) => [x < 0 ? x + 360 : x, y]);
    return [east, east.map(([x, y]) => [x - 360, y])];
  };
  const fixPolygon = (poly: GeoJSON.Position[][]): GeoJSON.Position[][][] => {
    const [outer, ...holes] = poly;
    return fixRing(outer).map((r) => [r, ...holes]);
  };
  return {
    ...fc,
    features: fc.features.filter((f) => f.id !== '010').map((f) => { // drop Antarctica
      const g = f.geometry;
      if (g?.type === 'Polygon') return { ...f, geometry: { type: 'MultiPolygon', coordinates: fixPolygon(g.coordinates) } };
      if (g?.type === 'MultiPolygon') return { ...f, geometry: { type: 'MultiPolygon', coordinates: g.coordinates.flatMap(fixPolygon) } };
      return f;
    }),
  };
}

/* ------------------------------------------------- departure airport memory */

const ORIGIN_KEY = 'fc-origin';
const GEO_KEY = 'fc-geo';
type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
export type GeoState = 'unasked' | 'resolved' | 'denied' | 'unavailable' | 'dismissed';

export function readSavedOrigin(storage: StorageLike | null): AirportRef | null {
  try {
    const raw = storage?.getItem(ORIGIN_KEY);
    const v = raw ? JSON.parse(raw) : null;
    return v && typeof v.code === 'string' && /^[A-Z]{3}$/.test(v.code) && typeof v.city === 'string' ? v as AirportRef : null;
  } catch { return null; }
}
export function saveOrigin(storage: StorageLike | null, airport: AirportRef | null) {
  try {
    if (airport) storage?.setItem(ORIGIN_KEY, JSON.stringify({ code: airport.code, name: airport.name, city: airport.city, country: airport.country, country_code: airport.country_code, lat: airport.lat, lon: airport.lon }));
    else storage?.removeItem(ORIGIN_KEY);
  } catch { /* storage blocked */ }
}
/** Only the outcome is remembered (never coordinates), so we do not ask repeatedly. */
export function readGeoState(storage: StorageLike | null): GeoState {
  try { const v = storage?.getItem(GEO_KEY); return v === 'resolved' || v === 'denied' || v === 'unavailable' || v === 'dismissed' ? v : 'unasked'; } catch { return 'unasked'; }
}
export function writeGeoState(storage: StorageLike | null, state: GeoState) {
  try { storage?.setItem(GEO_KEY, state); } catch { /* storage blocked */ }
}

/** Pick a confident default: the nearest commercial airport within 120 km. */
export function confidentNearest<T extends { distance_km?: number }>(candidates: T[], maxKm = 120): T | null {
  const first = candidates[0];
  return first && first.distance_km != null && first.distance_km <= maxKm ? first : null;
}
