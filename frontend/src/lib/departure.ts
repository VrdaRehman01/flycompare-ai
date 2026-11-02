import { useCallback, useEffect, useRef, useState } from 'react';
import type { LocationStatus } from '../components/AirportField';
import { api } from './api';
import { rememberAirports, toRef } from './format';
import { confidentNearest, readGeoState, readSavedOrigin, roundCoord, saveOrigin, writeGeoState, type GeoState } from './geo';
import { safeLocalStorage } from './theme';
import type { Airport, AirportRef } from './types';

async function permissionState(): Promise<PermissionState | 'unsupported'> {
  try {
    if (!navigator.permissions?.query) return 'unsupported';
    return (await navigator.permissions.query({ name: 'geolocation' as PermissionName })).state;
  } catch { return 'unsupported'; }
}

/**
 * Departure airport selection:
 * 1. The airport the visitor last chose (stored in this browser), else
 * 2. their account's home airport, else
 * 3. nothing — we never assume a city.
 * Location is only requested when the visitor asks for it, or silently reused
 * when they already granted permission earlier. Only the resulting airport is
 * remembered; coordinates are rounded to ~1 km, sent once, and never stored.
 */
export function useDepartureAirport(homeAirport: string | null | undefined) {
  const storage = safeLocalStorage();
  const [origin, setOriginState] = useState<AirportRef | null>(() => readSavedOrigin(storage));
  const [geoState, setGeoState] = useState<GeoState>(() => readGeoState(storage));
  const [status, setStatus] = useState<LocationStatus>({ state: 'idle' });
  const [nearby, setNearby] = useState<Airport[]>([]);
  const touched = useRef(!!origin);

  const setOrigin = useCallback((a: AirportRef | null) => {
    touched.current = true;
    setOriginState(a);
    saveOrigin(safeLocalStorage(), a);
  }, []);

  const locate = useCallback((applyIfConfident = true) => {
    if (!('geolocation' in navigator)) {
      setStatus({ state: 'unavailable', message: 'Location is not available in this browser. Please choose an airport.' });
      return;
    }
    setStatus({ state: 'locating', message: 'Finding the nearest airport…' });
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const list = await api<Airport[]>(`/api/airports/nearby?lat=${roundCoord(pos.coords.latitude)}&lon=${roundCoord(pos.coords.longitude)}&limit=4`);
          rememberAirports(list);
          setNearby(list);
          const best = confidentNearest(list);
          writeGeoState(safeLocalStorage(), 'resolved');
          setGeoState('resolved');
          if (best && applyIfConfident) {
            setOrigin(toRef(best));
            setStatus({ state: 'idle', message: `Nearest airport: ${best.city} (${best.code}). You can change it at any time.` });
          } else if (!best) {
            setStatus({ state: 'none-nearby', message: 'No commercial airport found within 120 km. Please choose your departure airport.' });
          } else setStatus({ state: 'idle' });
        } catch {
          setStatus({ state: 'error', message: 'Could not look up nearby airports. Please choose an airport.' });
        }
      },
      (err) => {
        const denied = err.code === err.PERMISSION_DENIED;
        const next: GeoState = denied ? 'denied' : 'unavailable';
        writeGeoState(safeLocalStorage(), next);
        setGeoState(next);
        setStatus({ state: denied ? 'denied' : 'unavailable', message: denied ? 'Location permission was declined. Choose your departure airport instead.' : 'Your location could not be determined. Please choose an airport.' });
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60 * 60 * 1000 },
    );
  }, [setOrigin]);

  // Reuse a previously granted permission silently (no prompt is shown).
  useEffect(() => {
    if (origin) return;
    void permissionState().then((state) => { if (state === 'granted' && !touched.current) locate(true); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fall back to the account's home airport when nothing else is known.
  useEffect(() => {
    if (touched.current || origin || !homeAirport) return;
    api<Airport[]>(`/api/airports/lookup?codes=${homeAirport}`).then((r) => { if (r[0] && !touched.current) { rememberAirports(r); setOriginState(toRef(r[0])); } }).catch(() => {});
  }, [homeAirport, origin]);

  return { origin, setOrigin, locate, status, geoState, nearby, dismissPrompt: () => { writeGeoState(safeLocalStorage(), 'dismissed'); setGeoState('dismissed'); } };
}
