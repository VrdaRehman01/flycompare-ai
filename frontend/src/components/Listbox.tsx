import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronDown } from 'lucide-react';

export type Option<T extends string> = { value: T; label: string; hint?: string; disabled?: boolean };

/**
 * Accessible single-select dropdown used for every select-style control, so
 * all dropdowns share styling, positioning and keyboard behaviour:
 * Enter/Space/ArrowDown open, arrows move, Home/End jump, typing a letter
 * jumps to the next matching option, Enter selects, Escape closes.
 */
export function Listbox<T extends string>({ value, options, onChange, label, icon, className = '', align = 'left', compact }: {
  value: T; options: Option<T>[]; onChange: (v: T) => void; label: string; icon?: ReactNode; className?: string; align?: 'left' | 'right'; compact?: boolean;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    setActive(Math.max(0, options.findIndex((o) => o.value === value)));
    const onDown = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open, options, value]);
  useEffect(() => { if (open) list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' }); }, [active, open]);

  const move = (dir: 1 | -1) => setActive((i) => {
    let n = i;
    for (let k = 0; k < options.length; k++) { n = (n + dir + options.length) % options.length; if (!options[n].disabled) return n; }
    return i;
  });
  const choose = (i: number) => { const o = options[i]; if (!o || o.disabled) return; onChange(o.value); setOpen(false); };

  return (
    <div className={`listbox ${compact ? 'compact' : ''} ${className}`} ref={wrap}>
      <button
        type="button" className="listbox-button" aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`} aria-label={`${label}: ${selected?.label ?? ''}`}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (!open && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); setOpen(true); return; }
          if (!open) return;
          if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
          else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
          else if (e.key === 'End') { e.preventDefault(); setActive(options.length - 1); }
          else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(active); }
          else if (e.key === 'Escape' || e.key === 'Tab') setOpen(false);
          else if (e.key.length === 1) {
            const k = e.key.toLowerCase();
            const n = options.findIndex((o, i) => i > active && o.label.toLowerCase().startsWith(k));
            const m = n >= 0 ? n : options.findIndex((o) => o.label.toLowerCase().startsWith(k));
            if (m >= 0) setActive(m);
          }
        }}
      >
        {icon}<span className="listbox-value">{selected?.label ?? 'Select'}</span><ChevronDown size={14} className={open ? 'flip' : ''} />
      </button>
      {open && (
        <ul className={`listbox-menu card align-${align}`} role="listbox" id={`${id}-list`} aria-label={label} ref={list} aria-activedescendant={`${id}-o${active}`}>
          {options.map((o, i) => (
            <li key={o.value} id={`${id}-o${i}`} data-index={i} role="option" aria-selected={o.value === value} aria-disabled={o.disabled}
              className={`${i === active ? 'active' : ''} ${o.value === value ? 'selected' : ''} ${o.disabled ? 'disabled' : ''}`}
              onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); choose(i); }}>
              <span><b>{o.label}</b>{o.hint && <small>{o.hint}</small>}</span>{o.value === value && <Check size={14} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
