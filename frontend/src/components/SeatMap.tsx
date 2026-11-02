import { useMemo, useState } from 'react';
import { DoorOpen } from 'lucide-react';
import { money } from '../lib/format';
import type { SeatElement, SeatMap as SeatMapData } from '../lib/types';

type Seat = Extract<SeatElement, { designator: string }>;
export type SeatChoice = { segmentId: string; passengerId: string; designator: string; serviceId: string; amount: number | null; currency: string | null };

const isSeat = (e: SeatElement): e is Seat => e.type === 'seat';
const rowNumber = (row: SeatElement[][]) => {
  for (const section of row) for (const e of section) if (isSeat(e) && e.designator) return e.designator.replace(/\D+$/, '');
  return '';
};

/**
 * Seat map for one segment, drawn from the provider's layout. Only seats the
 * provider marks as purchasable can be chosen; prices are the provider's.
 */
export function SeatMap({ map, passengers, passengerLabel, choices, onChoose }: {
  map: SeatMapData; passengers: string[]; passengerLabel: (id: string) => string;
  choices: SeatChoice[]; onChoose: (choice: SeatChoice | { segmentId: string; passengerId: string; designator: null }) => void;
}) {
  const segmentId = map.segment_id ?? '';
  const [active, setActive] = useState(passengers[0] ?? '');
  const mine = choices.filter((c) => c.segmentId === segmentId);
  const takenBy = useMemo(() => new Map(mine.map((c) => [c.designator, c.passengerId])), [mine]);
  const passengerIndex = (id: string) => passengers.indexOf(id) + 1;

  const pick = (seat: Seat) => {
    const service = seat.services.find((s) => s.passenger_id === active);
    if (!service) return;
    const holder = takenBy.get(seat.designator);
    if (holder === active) { onChoose({ segmentId, passengerId: active, designator: null }); return; }
    if (holder) return;
    onChoose({ segmentId, passengerId: active, designator: seat.designator, serviceId: service.id, amount: service.amount, currency: service.currency });
    const next = passengers.find((p) => p !== active && !mine.some((c) => c.passengerId === p));
    if (next) setActive(next);
  };

  return (
    <div className="seatmap">
      {passengers.length > 1 && (
        <div className="seat-passengers" role="radiogroup" aria-label="Choose a seat for">
          {passengers.map((p) => {
            const choice = mine.find((c) => c.passengerId === p);
            return (
              <button key={p} role="radio" aria-checked={active === p} className={active === p ? 'active' : ''} onClick={() => setActive(p)}>
                <span className="seat-dot">{passengerIndex(p)}</span>{passengerLabel(p)}<small>{choice ? choice.designator : 'No seat'}</small>
              </button>
            );
          })}
        </div>
      )}
      <ul className="seat-legend" aria-label="Legend">
        <li><i className="seat free" /> Available</li>
        <li><i className="seat paid" /> Available (fee)</li>
        <li><i className="seat selected" /> Selected</li>
        <li><i className="seat taken" /> Unavailable</li>
        <li><i className="exit-mark"><DoorOpen size={11} /></i> Exit row</li>
      </ul>
      {map.cabins.map((cabin, ci) => (
        <div key={ci} className="cabin" aria-label={`${cabin.cabin_class ?? 'Cabin'}${cabin.deck ? ' · upper deck' : ''}`}>
          {(cabin.cabin_class || map.cabins.length > 1) && <div className="cabin-label">{(cabin.cabin_class ?? 'Cabin').replace('_', ' ')}{cabin.deck ? ' · upper deck' : ''}</div>}
          <div className="seat-rows">
            {cabin.rows.map((row, ri) => {
              const exit = row.some((section) => section.some((e) => e.type === 'exit_row'));
              const num = rowNumber(row);
              return (
                <div key={ri} className={`seat-row ${exit ? 'exit' : ''}`}>
                  <span className="row-num">{num}</span>
                  {row.map((section, si) => (
                    <div key={si} className="seat-section">
                      {section.map((e, ei) => {
                        if (!isSeat(e)) {
                          if (e.type === 'exit_row') return <span key={ei} className="exit-mark" title="Exit row"><DoorOpen size={12} /></span>;
                          if (e.type === 'empty') return <span key={ei} className="seat-gap" />;
                          return <span key={ei} className={`facility ${e.type}`} title={e.type.replace('_', ' ')}>{e.type === 'lavatory' ? 'WC' : e.type === 'galley' ? 'G' : ''}</span>;
                        }
                        const service = e.services.find((s) => s.passenger_id === active);
                        const holder = takenBy.get(e.designator);
                        const selectable = !!service && (!holder || holder === active);
                        const fee = service?.amount ?? null;
                        const cls = holder ? 'selected' : !e.available || !service ? 'taken' : fee ? 'paid' : 'free';
                        const label = `Seat ${e.designator}${holder ? `, selected for passenger ${passengerIndex(holder)}` : !selectable ? ', unavailable' : fee ? `, ${money(fee, service!.currency ?? 'USD', 2)}` : ', no fee'}${e.disclosures.length ? `. ${e.disclosures.join('. ')}` : ''}`;
                        return (
                          <button key={ei} className={`seat ${cls}`} disabled={!selectable} onClick={() => pick(e)} aria-label={label} title={label} aria-pressed={!!holder}>
                            {holder ? passengerIndex(holder) : e.designator.replace(/^\d+/, '')}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                  <span className="row-num">{num}</span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
