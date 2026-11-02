import { useEffect, useState, type ReactNode } from 'react';
import { BedDouble, MapPin, Star, Users } from 'lucide-react';
import { DestinationPhoto } from './DestinationCard';
import { convert } from '../lib/currency';
import { lookupLocation, readTrip, writeTrip, type Trip } from '../lib/travel';
import type { AirportRef, DataStatus } from '../lib/types';
import { usePrefs } from '../state';
import { Stepper, usePopover } from './Pickers';
import { Notice, StatusPill } from './ui';

/**
 * Page header shared by the travel pages: copy and tabs beside a photo of the chosen
 * destination (or a decorative illustration), with the search panel underneath.
 */
export function TravelHero({ icon, eyebrow, title, subtitle, tabs, children, place, art }: {
  icon: ReactNode; eyebrow: string; title: string; subtitle: string; tabs?: ReactNode; children?: ReactNode;
  place?: AirportRef | null; art?: ReactNode;
}) {
  const key = place?.country_code ? `${place.city}|${place.country_code}` : null;
  return (
    <section className="travel-hero">
      <div className="travel-hero-top">
        <div className="travel-hero-copy">
          <span className="travel-eyebrow">{icon} {eyebrow}</span>
          <h1>{title}</h1>
          <p>{subtitle}</p>
          {tabs && <div className="travel-tabs">{tabs}</div>}
        </div>
        <div className="travel-hero-visual" aria-hidden={!key}>
          {key && place ? (
            <>
              <DestinationPhoto dest={{ key, city: place.city, country: place.country }} eager />
              <span className="hero-place"><MapPin size={13} /> {place.city}, {place.country}</span>
            </>
          ) : <span className="hero-art">{art ?? icon}</span>}
        </div>
      </div>
      {children && <div className="card travel-search">{children}</div>}
    </section>
  );
}

export function ProviderNotice({ status, notice }: { status: DataStatus; notice: string | null }) {
  if (!notice && status === 'live') return null;
  return <Notice kind={status === 'demo' ? 'warn' : 'info'}><StatusPill status={status} /> {notice}</Notice>;
}

export function Stars({ n }: { n: number | null }) {
  if (!n) return null;
  return <span className="stars" aria-label={`${n}-star`} title={`${n}-star`}>{Array.from({ length: n }, (_, i) => <Star key={i} size={12} />)}</span>;
}

export function GuestPicker({ adults, children, rooms, onChange, showRooms = true, maxAdults = 16 }: {
  adults: number; children: number; rooms?: number; onChange: (v: { adults: number; children: number; rooms: number }) => void; showRooms?: boolean; maxAdults?: number;
}) {
  const { open, setOpen, ref } = usePopover();
  const r = rooms ?? 1;
  const summary = `${adults} adult${adults === 1 ? '' : 's'}${children ? `, ${children} child${children === 1 ? '' : 'ren'}` : ''}${showRooms ? ` · ${r} room${r === 1 ? '' : 's'}` : ''}`;
  return (
    <div className="popover-wrap" ref={ref}>
      <button type="button" className="pill-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {showRooms ? <BedDouble size={14} /> : <Users size={14} />}<span>{summary}</span>
      </button>
      {open && (
        <div className="popover card passenger-popover" role="dialog" aria-label="Guests">
          <Stepper label="Adults" hint="18 years and over" value={adults} min={Math.max(1, r)} max={maxAdults} onChange={(n) => onChange({ adults: n, children, rooms: r })} />
          <Stepper label="Children" hint="Under 18" value={children} min={0} max={8} onChange={(n) => onChange({ adults, children: n, rooms: r })} />
          {showRooms && <Stepper label="Rooms" hint="At least one adult per room" value={r} min={1} max={Math.min(8, adults)} onChange={(n) => onChange({ adults, children, rooms: n })} />}
          <div className="popover-actions"><button type="button" className="btn btn-primary" onClick={() => setOpen(false)}>Done</button></div>
        </div>
      )}
    </div>
  );
}

/**
 * The shared trip (destination, dates, party) for this tab. A location in the URL
 * wins over the remembered destination. Changes are remembered for other pages.
 */
export function useTrip(routeLocation?: string) {
  const [trip, setTripState] = useState<Trip>(readTrip);
  useEffect(() => {
    if (!routeLocation) return;
    let live = true;
    lookupLocation(routeLocation).then((a) => { if (live && a) setTripState((t) => ({ ...t, destination: a })); }).catch(() => {});
    return () => { live = false; };
  }, [routeLocation]);
  useEffect(() => { writeTrip(trip); }, [trip]);
  const update = (patch: Partial<Trip>) => setTripState((t) => ({ ...t, ...patch }));
  return [trip, update] as const;
}

/**
 * Converts amounts into one currency so different products can be added up.
 * Uses the visitor's display currency when set, otherwise `fallback`.
 * Returns null for an amount whose rate is not available yet.
 */
export function useConverter(fallback: string) {
  const { displayCurrency, ratesFor } = usePrefs();
  const target = displayCurrency ?? fallback;
  return {
    currency: target,
    to: (amount: number, from: string): number | null => (from === target ? amount : convert(amount, from, target, ratesFor(from) ?? null)),
  };
}

export const destinationLabel = (a: AirportRef | null) => (a ? `${a.city}, ${a.country}` : 'your destination');
