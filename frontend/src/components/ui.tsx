import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CircleHelp, Info, X } from 'lucide-react';
import { convert } from '../lib/currency';
import { money } from '../lib/format';
import type { DataStatus } from '../lib/types';
import { usePrefs } from '../state';

export function Modal({ title, onClose, children, width = 440 }: { title: string; onClose: () => void; children: ReactNode; width?: number }) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLElement>('input, button:not(.modal-close), select')?.focus();
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; previous?.focus?.(); };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal card" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={panel} style={{ maxWidth: width }}>
        <div className="modal-head"><h2 id={titleId}>{title}</h2><button className="modal-close icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, body, confirmLabel, danger, onConfirm, onCancel, busy }: { title: string; body: ReactNode; confirmLabel: string; danger?: boolean; onConfirm: () => void; onCancel: () => void; busy?: boolean }) {
  return (
    <Modal title={title} onClose={onCancel}>
      <div className="modal-body">{body}</div>
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
        <button className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm} disabled={busy}>{busy ? <span className="spinner" /> : null}{confirmLabel}</button>
      </div>
    </Modal>
  );
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'error' | 'warn' | 'success'; children: ReactNode }) {
  const Icon = kind === 'error' ? CircleHelp : kind === 'warn' ? AlertTriangle : Info;
  return <div className={`notice ${kind}`} role={kind === 'error' ? 'alert' : undefined}><Icon size={16} /><div>{children}</div></div>;
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty-state">{icon}<h3>{title}</h3>{children && <p>{children}</p>}{action}</div>;
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading-block"><span className="spinner dark" /> {label}</div>;
}

export function StatusPill({ status }: { status: DataStatus | string | null | undefined }) {
  if (!status) return null;
  const text = status === 'live' ? 'Live' : status === 'recent' ? 'Recent fare' : status === 'test' ? 'Test data' : status === 'demo' ? 'Demo data' : 'Source not recorded';
  const title = status === 'test' ? 'Duffel test environment: sandbox offers, not real prices or bookable tickets'
    : status === 'demo' ? 'Simulated for development; not real offers'
    : status === 'recent' ? 'Real fare found by Aviasales users in the last few days; confirm the price on the booking site'
    : status === 'live' ? 'Live provider data; revalidate before booking' : 'Searched before FlyCompare recorded the data source';
  return <span className={`status-pill ${status}`} title={title}>{text}</span>;
}

/**
 * Shows a provider price. When the visitor picked a display currency and a
 * reference rate exists, the converted value is shown as approximate alongside
 * the original amount, which always remains the authoritative price.
 */
export function Price({ amount, currency, className = '', digits = 0, inline = false }: { amount: number; currency: string; className?: string; digits?: number; inline?: boolean }) {
  const { displayCurrency, ratesFor } = usePrefs();
  const original = money(amount, currency, digits);
  if (!displayCurrency || displayCurrency === currency) return <strong className={`price ${className}`}>{original}</strong>;
  const rates = ratesFor(currency);
  const converted = convert(amount, currency, displayCurrency, rates ?? null);
  if (converted == null) {
    const why = rates === undefined ? 'Loading exchange rate…' : `No reference rate between ${currency} and ${displayCurrency}; showing the original price.`;
    return <strong className={`price ${className}`} title={why}>{original}</strong>;
  }
  const title = `Approximate conversion using ${rates?.source ?? 'reference rates'} (${rates?.date}). The original offer is ${original}.`;
  if (inline) return <strong className={`price ${className}`} title={title}>≈ {money(converted, displayCurrency, digits)} <small className="price-original">({original})</small></strong>;
  return (
    <span className={`price-stack ${className}`} title={title}>
      <strong className="price">≈ {money(converted, displayCurrency, digits)}</strong>
      <small className="price-original">{original} original</small>
    </span>
  );
}

/**
 * For places that need numbers rather than a <Price> element (charts, stat tiles):
 * converts amounts from `from` into the display currency when a rate is available,
 * otherwise leaves them in `from`. `approx` tells the caller to mark values with ≈.
 */
export function useDisplayCurrency(from: string | undefined) {
  const { displayCurrency, ratesFor } = usePrefs();
  const rates = from && displayCurrency && displayCurrency !== from ? ratesFor(from) : null;
  const rate = from && displayCurrency && rates ? convert(1, from, displayCurrency, rates) : null;
  const currency = rate != null ? displayCurrency! : from ?? '';
  return {
    currency,
    approx: rate != null,
    source: rate != null ? `${rates!.source}, ${rates!.date}` : null,
    value: (amount: number) => (rate != null ? amount * rate : amount),
    format: (amount: number, digits = 0) => `${rate != null ? '≈ ' : ''}${money(rate != null ? amount * rate : amount, currency, digits)}`,
  };
}

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = window.setTimeout(() => setV(value), ms); return () => window.clearTimeout(t); }, [value, ms]);
  return v;
}

export function SegmentedControl<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => <button type="button" key={o.value} role="radio" aria-checked={value === o.value} className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}
