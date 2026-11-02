import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Minus, Plus, Users } from 'lucide-react';
import { MAX_SEATS, passengerSummary } from '../lib/validation';
import type { Passengers } from '../lib/types';

export function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);
  return { open, setOpen, ref };
}

export { DateField, type FareContext } from './DateField';

export function Stepper({ label, hint, value, min, max, onChange }: { label: string; hint: string; value: number; min: number; max: number; onChange: (n: number) => void }) {
  return (
    <div className="stepper">
      <span><b>{label}</b><small>{hint}</small></span>
      <div className="stepper-controls">
        <button type="button" className="icon-btn" onClick={() => onChange(value - 1)} disabled={value <= min} aria-label={`Fewer ${label.toLowerCase()}`}><Minus size={14} /></button>
        <output aria-live="polite" aria-label={label}>{value}</output>
        <button type="button" className="icon-btn" onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={`More ${label.toLowerCase()}`}><Plus size={14} /></button>
      </div>
    </div>
  );
}

export function PassengerPicker({ value, onChange, error, children }: { value: Passengers; onChange: (p: Passengers) => void; error?: string; children?: ReactNode }) {
  const { open, setOpen, ref } = usePopover();
  const seats = value.adults + value.childAges.length;
  const set = (patch: Partial<Passengers>) => {
    const next = { ...value, ...patch };
    next.infants = Math.min(next.infants, next.adults); // keep infants ≤ adults when adults decrease
    onChange(next);
  };
  return (
    <div className="popover-wrap" ref={ref}>
      <button type="button" className={`pill-trigger ${error ? 'invalid' : ''}`} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <Users size={14} /><span>{passengerSummary(value)}</span>
      </button>
      {open && (
        <div className="popover card passenger-popover" role="dialog" aria-label="Passengers">
          <Stepper label="Adults" hint="18 years and over" value={value.adults} min={1} max={MAX_SEATS - value.childAges.length} onChange={(n) => set({ adults: n })} />
          <Stepper label="Children" hint="2–17 years, own seat" value={value.childAges.length} min={0} max={MAX_SEATS - value.adults}
            onChange={(n) => set({ childAges: n > value.childAges.length ? [...value.childAges, 8] : value.childAges.slice(0, n) })} />
          {value.childAges.length > 0 && (
            <div className="child-ages">
              {value.childAges.map((age, i) => (
                <label key={i}><span>Child {i + 1} age</span>
                  <select value={age} onChange={(e) => set({ childAges: value.childAges.map((a, j) => (j === i ? Number(e.target.value) : a)) })}>
                    {Array.from({ length: 16 }, (_, k) => k + 2).map((a) => <option key={a} value={a}>{a}</option>)}
                  </select>
                </label>
              ))}
            </div>
          )}
          <Stepper label="Infants" hint="Under 2, on an adult’s lap" value={value.infants} min={0} max={value.adults} onChange={(n) => set({ infants: n })} />
          <p className="muted small">Up to {MAX_SEATS} seated passengers ({seats} selected). One lap infant per adult. Ages are at the time of travel and affect the fare.</p>
          {children}
          <div className="popover-actions"><button type="button" className="btn btn-primary" onClick={() => setOpen(false)}>Done</button></div>
        </div>
      )}
    </div>
  );
}
