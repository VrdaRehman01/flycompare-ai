import { useState } from 'react';
import { Briefcase, ChevronDown, Clock3, Heart, Luggage, Plane, ShieldCheck, Wifi } from 'lucide-react';
import { AirlineLogo } from '../illustrations';
import { bagOf, bagText, cityOf, dayOffset, durationLabel, legsOf, minutesBetween, shortDate, stopsLabel, timeOf } from '../lib/format';
import { SCORE_WEIGHTS, totalDurationOf, type ScoreParts } from '../lib/results';
import { writeSession } from '../lib/router';
import type { Flight, Itinerary } from '../lib/types';
import { Price, StatusPill } from './ui';

export const refundText = (r: boolean | null) => r == null ? 'Refund terms not supplied' : r ? 'Refundable' : 'Non-refundable';

export type DetailsTab = 'Baggage' | 'Fare conditions' | 'Aircraft' | 'Amenities' | 'Seats';
/** Open the details page on a given tab (read once by DetailsPage). */
export const preselectTab = (tab: DetailsTab) => writeSession('fc-details-tab', tab);

/** Wi-Fi as stated for every segment of the outbound journey; null when not supplied for all of them. */
export function wifiSummary(f: Flight): string | null {
  const segs = legsOf(f)[0]?.segments ?? [];
  const states = segs.map((s) => s.amenities?.wifi?.available);
  if (!segs.length || states.some((v) => v == null)) return null;
  if (states.every(Boolean)) return 'Wi-Fi on board';
  return states.some(Boolean) ? 'Wi-Fi on some flights' : 'No Wi-Fi';
}

export function LegRow({ leg, tag }: { leg: Itinerary; tag?: string }) {
  const offset = dayOffset(leg.departing_at, leg.arriving_at);
  const via = leg.segments.slice(0, -1).map((s) => s.destination).join(', ');
  return (
    <div className="leg-row">
      {tag && <span className="leg-tag">{tag}</span>}
      <div className="leg-time"><strong>{timeOf(leg.departing_at)}</strong><small>{leg.origin}</small></div>
      <div className="leg-line">
        <small>{durationLabel(leg.duration_minutes)}</small>
        <span className="line"><i /><Plane size={12} /></span>
        <small className={leg.stops === 0 ? 'direct' : ''}>{stopsLabel(leg.stops)}{via ? ` · ${via}` : ''}</small>
      </div>
      <div className="leg-time"><strong>{timeOf(leg.arriving_at)}{offset > 0 && <sup>+{offset}</sup>}</strong><small>{leg.destination}</small></div>
    </div>
  );
}

export function SegmentList({ leg, fallbackAirline, fallbackNumber }: { leg: Itinerary; fallbackAirline: string; fallbackNumber: string }) {
  if (!leg.segments.length) {
    return <div className="segment"><span className="seg-dot" /><div className="seg-main"><b>{leg.origin} → {leg.destination}</b><small>{fallbackAirline} · {fallbackNumber} · Segment details not provided</small></div></div>;
  }
  return (
    <>
      {leg.segments.map((s, j) => {
        const next = leg.segments[j + 1];
        const layover = next ? minutesBetween(s.arriving_at, next.departing_at) : null;
        return (
          <div key={j}>
            <div className="segment">
              <span className="seg-dot" />
              <div className="seg-main">
                <b>{timeOf(s.departing_at)} {cityOf(s.origin)} ({s.origin}) → {timeOf(s.arriving_at)} {cityOf(s.destination)} ({s.destination})</b>
                <small>{s.airline ?? fallbackAirline} · {s.flight_number ?? 'Flight number not provided'} · {s.aircraft ?? 'Aircraft not provided'}{s.cabin ? ` · ${s.cabin.replace('_', ' ')}` : ''}</small>
              </div>
              <span className="seg-dur">{durationLabel(s.duration_minutes)}</span>
            </div>
            {layover != null && <div className="layover"><Clock3 size={13} /> {layover > 0 ? `${durationLabel(layover)} connection in ${cityOf(s.destination)} (${s.destination})` : `Connection in ${s.destination}`}</div>}
          </div>
        );
      })}
    </>
  );
}

export function FlightCard({ f, passengers, badge, score, saved, onSave, onSelect }: { f: Flight; passengers: number; badge?: string; score?: ScoreParts; saved: boolean; onSave: () => void; onSelect: () => void }) {
  const [open, setOpen] = useState(false);
  const legs = legsOf(f);
  const checked = bagOf(f, 'checked'), carry = bagOf(f, 'carry_on');
  const wifi = wifiSummary(f);
  const brand = legs[0]?.fare_brand_name;
  const openTab = (tab: DetailsTab) => { preselectTab(tab); onSelect(); };
  return (
    <article className={`card flight-card ${open ? 'expanded' : ''}`}>
      <div className="fc-body">
        <div className="fc-airline"><AirlineLogo name={f.airline} src={f.airline_logo_url} /><div><b>{f.airline}</b><small>{f.flight_number}{brand ? ` · ${brand}` : ''}</small></div></div>
        <div className="fc-legs">{legs.map((leg, i) => <LegRow key={i} leg={leg} tag={legs.length === 2 ? (i === 0 ? 'OUT' : 'RET') : legs.length > 2 ? `FLIGHT ${i + 1}` : undefined} />)}</div>
        <div className="fc-price">
          <button className={`heart ${saved ? 'on' : ''}`} onClick={onSave} aria-pressed={saved} aria-label={saved ? 'Remove from saved flights' : 'Save flight'}><Heart size={16} /></button>
          {badge && <span className={`badge ${badge === 'Cheapest' ? 'green' : 'blue'}`}>{badge}</span>}
          <Price amount={f.price} currency={f.currency} />
          <small>Total · {legs.length > 2 ? 'multi-city' : legs.length > 1 ? 'round trip' : 'one way'}{passengers > 1 ? ` · ${passengers} travellers` : ''}</small>
          <button className="btn btn-primary" onClick={onSelect}>Select</button>
        </div>
      </div>
      <div className="fc-foot">
        <button className={`fc-chip ${f.refundable ? 'good' : ''}`} onClick={() => openTab('Fare conditions')}><ShieldCheck size={13} />{refundText(f.refundable)}</button>
        <button className={`fc-chip ${checked?.quantity ? 'good' : ''}`} onClick={() => openTab('Baggage')}><Luggage size={13} />Checked: {checked ? bagText(checked) : f.baggage_kg ? `${f.baggage_kg} kg` : 'not supplied'}</button>
        <button className="fc-chip" onClick={() => openTab('Baggage')}><Briefcase size={13} />Cabin: {carry ? bagText(carry) : 'not supplied'}</button>
        {wifi && <button className="fc-chip" onClick={() => openTab('Amenities')}><Wifi size={13} />{wifi}</button>}
        <StatusPill status={f.data_status} />
        <button className="details-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>{open ? 'Hide details' : 'Itinerary'} <ChevronDown size={14} className={open ? 'flip' : ''} /></button>
      </div>
      {open && (
        <div className="fc-expand">
          {legs.map((leg, i) => (
            <div key={i} className="fc-expand-leg">
              <b className="fc-expand-title">{legs.length > 2 ? `Flight ${i + 1}` : legs.length > 1 ? (i === 0 ? 'Outbound' : 'Return') : 'Journey'} · {shortDate(leg.departing_at)} · {durationLabel(leg.duration_minutes)}</b>
              <div className="segments"><SegmentList leg={leg} fallbackAirline={f.airline} fallbackNumber={f.flight_number} /></div>
            </div>
          ))}
          {score && (
            <div className="score-box">
              <b>Why this rank</b>
              <span>Price {Math.round(score.price * 100)}/100 × {SCORE_WEIGHTS.price * 100}%</span>
              <span>Journey time {Math.round(score.duration * 100)}/100 × {SCORE_WEIGHTS.duration * 100}% ({durationLabel(totalDurationOf(f))} total)</span>
              <span>Stops {Math.round(score.stops * 100)}/100 × {SCORE_WEIGHTS.stops * 100}%</span>
              <span>Checked bag {Math.round(score.bags * 100)}/100 × {SCORE_WEIGHTS.bags * 100}%{score.bags === 0.5 ? ' (not supplied)' : ''}</span>
              <span>Refundability {Math.round(score.flex * 100)}/100 × {SCORE_WEIGHTS.flex * 100}%{score.flex === 0.5 ? ' (not supplied)' : ''}</span>
              <small>0 = best in these results, 100 = worst. Lower total ranks higher.</small>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
