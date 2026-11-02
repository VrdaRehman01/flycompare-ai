import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { ArrowRight, Bookmark, Clock3, Eye, Heart, History, KeyRound, LogIn, Search, Settings, Trash2, User as UserIcon } from 'lucide-react';
import type { SearchRouteFn } from '../App';
import { DISPLAY_CURRENCIES } from '../components/Header';
import { AirportField } from '../components/AirportField';
import { Listbox } from '../components/Listbox';
import { ConfirmDialog, EmptyState, Loading, Modal, Notice, Price, StatusPill } from '../components/ui';
import { AirlineLogo } from '../illustrations';
import { DestinationPhoto } from '../components/DestinationCard';
import { api, errorText } from '../lib/api';
import { cityOf, dateTime, dayMonth, durationLabel, legsOf, stopsLabel, toRef, todayIso } from '../lib/format';
import { navigate, type AccountTab } from '../lib/router';
import { CABINS, type Airport, type AirportRef, type Flight, type HistoryItem, type Preferences, type SavedFlight, type SearchForm, type ThemePreference, type User } from '../lib/types';
import { useAuth, usePrefs, useToast } from '../state';

const TABS: { id: AccountTab; label: string; icon: ReactNode }[] = [
  { id: 'profile', label: 'Profile', icon: <UserIcon size={16} /> },
  { id: 'saved', label: 'Saved flights', icon: <Bookmark size={16} /> },
  { id: 'favourites', label: 'Favourites', icon: <Heart size={16} /> },
  { id: 'recent', label: 'Recently viewed', icon: <Eye size={16} /> },
  { id: 'history', label: 'Search history', icon: <History size={16} /> },
  { id: 'preferences', label: 'Preferences', icon: <Settings size={16} /> },
  { id: 'security', label: 'Security', icon: <KeyRound size={16} /> },
];

type Props = { tab: AccountTab; onOpenFlight: (f: Flight, q: SearchForm | null) => void; onSearchRoute: SearchRouteFn; onExplore: (code: string) => void };

export function AccountPage({ tab, onOpenFlight, onSearchRoute, onExplore }: Props) {
  const { user, ready, openAuth } = useAuth();
  if (!ready) return <div className="container page"><Loading /></div>;
  if (!user) {
    return (
      <div className="container page">
        <div className="page-head"><div><h1>Your travel space</h1><p>Everything works without an account. Sign in only to keep things in sync across devices.</p></div></div>
        <div className="card signin-cta">
          <LogIn size={26} />
          <div>
            <h3>Sign in to sync across devices</h3>
            <p>An account keeps your saved flights, favourite destinations, search history, preferences and personal insights on every device. Anything saved below moves into your account when you sign in.</p>
          </div>
          <div className="row-actions"><button className="btn btn-primary" onClick={() => openAuth('login')}>Sign in</button><button className="btn btn-soft" onClick={() => openAuth('register')}>Create account</button></div>
        </div>
        <div className="account-body">
          <SavedTab onOpenFlight={onOpenFlight} local />
          <FavouritesTab onExplore={onExplore} local />
        </div>
      </div>
    );
  }
  return (
    <div className="container page">
      <div className="page-head"><div><h1>My account</h1><p>Signed in as {user.email}</p></div></div>
      <div className="account-layout">
        <nav className="card account-nav" aria-label="Account sections">
          {TABS.map((t) => <button key={t.id} className={tab === t.id ? 'active' : ''} aria-current={tab === t.id ? 'page' : undefined} onClick={() => navigate({ page: 'account', tab: t.id })}>{t.icon}{t.label}</button>)}
        </nav>
        <div className="account-body">
          {tab === 'profile' && <ProfileTab user={user} />}
          {tab === 'saved' && <SavedTab onOpenFlight={onOpenFlight} />}
          {tab === 'favourites' && <FavouritesTab onExplore={onExplore} />}
          {tab === 'recent' && <RecentTab onOpenFlight={onOpenFlight} />}
          {tab === 'history' && <HistoryTab onSearchRoute={onSearchRoute} />}
          {tab === 'preferences' && <PreferencesTab user={user} />}
          {tab === 'security' && <SecurityTab />}
        </div>
      </div>
    </div>
  );
}

function Section({ title, sub, children, aside }: { title: string; sub?: string; children: ReactNode; aside?: ReactNode }) {
  return <section className="card panel"><div className="panel-head"><div><h3>{title}</h3>{sub && <p className="muted small">{sub}</p>}</div>{aside}</div>{children}</section>;
}

function ProfileTab({ user }: { user: User }) {
  const { setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const emailChanged = email.trim().toLowerCase() !== user.email;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const updated = await api<User>('/api/account/profile', { method: 'PATCH', body: { name, ...(emailChanged ? { email, current_password: password } : {}) } });
      setUser(updated);
      setPassword('');
      toast('success', 'Profile updated.');
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Profile" sub={`Member since ${dayMonth(user.created_at)} ${new Date(user.created_at).getFullYear()}`}>
      <form className="form narrow" onSubmit={submit}>
        <label className="form-field"><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} autoComplete="name" /></label>
        <label className="form-field"><span>Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} autoComplete="email" /></label>
        {emailChanged && <label className="form-field"><span>Current password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /><small>Required to change your sign-in email.</small></label>}
        {error && <Notice kind="error">{error}</Notice>}
        <div className="row-actions"><button className="btn btn-primary" disabled={busy || (name === user.name && !emailChanged)}>{busy && <span className="spinner" />}Save changes</button></div>
      </form>
    </Section>
  );
}

function FlightRow({ item, onOpen, onRemove, removeLabel }: { item: SavedFlight; onOpen: () => void; onRemove?: () => void; removeLabel?: string }) {
  const f = item.offer;
  const legs = legsOf(f);
  const past = f.departure_date < todayIso();
  return (
    <div className="saved-row">
      <AirlineLogo name={f.airline} src={f.airline_logo_url} />
      <div className="saved-main">
        <b>{legs[0].origin} <ArrowRight size={12} /> {legs[0].destination}{legs.length > 1 ? ' · round trip' : ''}</b>
        <small>{f.airline} · {dayMonth(legs[0].departing_at)}{legs[1] ? ` – ${dayMonth(legs[1].departing_at)}` : ''} · {stopsLabel(legs[0].stops)} · {durationLabel(legs[0].duration_minutes)}</small>
        <small className="muted">Price captured {dateTime(f.retrieved_at)} · may have changed{past ? ' · travel date has passed' : ''}</small>
      </div>
      <div className="saved-price"><Price amount={f.price} currency={f.currency} /><StatusPill status={f.data_status} /></div>
      <div className="saved-actions">
        <button className="btn btn-soft" onClick={onOpen}>View</button>
        {onRemove && <button className="icon-btn danger" onClick={onRemove} aria-label={removeLabel} title={removeLabel}><Trash2 size={16} /></button>}
      </div>
    </div>
  );
}

function SavedTab({ onOpenFlight, local }: { onOpenFlight: Props['onOpenFlight']; local?: boolean }) {
  const { saved, refreshSaved, toggleSaved } = useAuth();
  const [loaded, setLoaded] = useState(false);
  const [confirm, setConfirm] = useState<SavedFlight | null>(null);
  useEffect(() => { void refreshSaved().finally(() => setLoaded(true)); }, [refreshSaved]);
  return (
    <Section title={local ? 'Saved in this browser' : 'Saved flights'} sub={local ? 'Flights you saved on this device. Prices and availability can change.' : 'Snapshots of offers you saved to compare. Not bookings — prices and availability can change.'}>
      {!loaded && !saved.length ? <Loading /> : saved.length ? (
        <div className="saved-list">{saved.map((s) => <FlightRow key={s.id} item={s} onOpen={() => onOpenFlight(s.offer, s.search)} onRemove={() => setConfirm(s)} removeLabel="Remove saved flight" />)}</div>
      ) : <EmptyState icon={<Bookmark size={28} />} title="No saved flights yet" action={<button className="btn btn-primary" onClick={() => navigate({ page: 'home' })}><Search size={15} /> Search flights</button>}>
        <span className="onboard-steps"><span>1. Search for a route</span><span>2. Tap the ♡ on any result</span><span>3. Compare it here later</span></span>
      </EmptyState>}
      {confirm && <ConfirmDialog title="Remove saved flight?" body={<p>{confirm.offer.airline} {confirm.offer.origin} → {confirm.offer.destination} will be removed from your saved flights.</p>} confirmLabel="Remove" danger onCancel={() => setConfirm(null)} onConfirm={() => { void toggleSaved(confirm.offer, confirm.search); setConfirm(null); }} />}
    </Section>
  );
}

function FavouritesTab({ onExplore, local }: { onExplore: (code: string) => void; local?: boolean }) {
  const { favourites, toggleFavourite } = useAuth();
  const [airports, setAirports] = useState<Record<string, Airport>>({});
  useEffect(() => {
    const missing = favourites.filter((c) => !airports[c]);
    if (!missing.length) return;
    api<Airport[]>(`/api/airports/lookup?codes=${missing.join(',')}`).then((list) => setAirports((all) => ({ ...all, ...Object.fromEntries(list.map((a) => [a.code, a])) }))).catch(() => {});
  }, [favourites]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Section title={local ? 'Favourite destinations in this browser' : 'Favourite destinations'} sub="Destinations you marked with a heart.">
      {favourites.length ? (
        <div className="fav-grid">
          {favourites.map((code) => {
            const a = airports[code];
            return (
              <div key={code} className="fav-card">
                <div className="fav-art">{a ? <DestinationPhoto dest={{ key: `${a.city}|${a.country_code}`, city: a.city, country: a.country }} /> : null}</div>
                <div className="fav-body"><b>{a?.city ?? cityOf(code)}</b><small>{a ? `${a.country} · ${a.name}` : code}</small></div>
                <div className="row-actions"><button className="btn btn-soft" onClick={() => onExplore(code)}>Plan a search</button><button className="icon-btn danger" onClick={() => void toggleFavourite(code)} aria-label={`Remove ${code} from favourites`}><Trash2 size={16} /></button></div>
              </div>
            );
          })}
        </div>
      ) : <EmptyState icon={<Heart size={28} />} title="No favourites yet" action={<button className="btn btn-primary" onClick={() => navigate({ page: 'destinations' })}>Explore destinations</button>}>Tap the heart on any destination to keep it here.</EmptyState>}
    </Section>
  );
}

function RecentTab({ onOpenFlight }: { onOpenFlight: Props['onOpenFlight'] }) {
  const toast = useToast();
  const [items, setItems] = useState<SavedFlight[] | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState('');
  const load = () => api<SavedFlight[]>('/api/account/recently-viewed').then(setItems).catch((err) => setError(errorText(err)));
  useEffect(() => { void load(); }, []);
  const clear = async () => {
    try { await api('/api/account/recently-viewed', { method: 'DELETE' }); setItems([]); toast('info', 'Recently viewed flights cleared.'); } catch (err) { toast('error', errorText(err)); }
    setConfirm(false);
  };
  return (
    <Section title="Recently viewed" sub="The last 20 flights you opened while signed in." aside={items?.length ? <button className="btn btn-ghost" onClick={() => setConfirm(true)}>Clear</button> : undefined}>
      {error ? <Notice kind="error">{error}</Notice> : !items ? <Loading /> : items.length ? (
        <div className="saved-list">{items.map((s) => <FlightRow key={s.id} item={s} onOpen={() => onOpenFlight(s.offer, s.search)} />)}</div>
      ) : <EmptyState icon={<Eye size={28} />} title="Nothing viewed yet">Flights you open from search results will appear here.</EmptyState>}
      {confirm && <ConfirmDialog title="Clear recently viewed?" body={<p>This removes your recently viewed flight list. Saved flights are not affected.</p>} confirmLabel="Clear list" danger onCancel={() => setConfirm(false)} onConfirm={() => void clear()} />}
    </Section>
  );
}

function HistoryTab({ onSearchRoute }: { onSearchRoute: SearchRouteFn }) {
  const toast = useToast();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { api<HistoryItem[]>('/api/account/history?limit=200').then(setItems).catch((err) => setError(errorText(err))); }, []);
  const clear = async () => {
    try { await api('/api/account/history', { method: 'DELETE' }); setItems([]); toast('info', 'Search history cleared from your account.'); } catch (err) { toast('error', errorText(err)); }
    setConfirm(false);
  };
  return (
    <Section title="Search history" sub="Searches made while signed in. Used for your personal insights." aside={items?.length ? <button className="btn btn-ghost" onClick={() => setConfirm(true)}>Clear history</button> : undefined}>
      {error ? <Notice kind="error">{error}</Notice> : !items ? <Loading /> : items.length ? (
        <div className="table">
          <div className="tr th history-tr"><span>Route</span><span>Dates</span><span>Cabin</span><span>Offers</span><span>Searched</span><span /></div>
          {items.map((h) => {
            const canRepeat = !!(h.origin_code && h.destination_code);
            const future = h.departure_date >= todayIso();
            return (
              <div className="tr history-tr" key={h.id}>
                <b>{h.origin_code ?? h.origin} <ArrowRight size={12} /> {h.destination_code ?? h.destination}</b>
                <span>{dayMonth(h.departure_date)}{h.return_date ? ` – ${dayMonth(h.return_date)}` : ' · one way'}</span>
                <span>{h.cabin} · {h.passengers}</span>
                <span>{h.result_count} <StatusPill status={h.data_status} /></span>
                <span className="muted">{dateTime(h.created_at)}</span>
                <span>{canRepeat && <button className="link-btn small" onClick={() => onSearchRoute(h.origin_code!, h.destination_code!, future ? { departure: h.departure_date, returnDate: h.return_date, tripType: h.trip_type } : { tripType: h.trip_type })}><Clock3 size={12} /> {future ? 'Search again' : 'New dates'}</button>}</span>
              </div>
            );
          })}
        </div>
      ) : <EmptyState icon={<History size={28} />} title="No searches yet">Searches you make while signed in are listed here.</EmptyState>}
      {confirm && <ConfirmDialog title="Clear search history?" body={<p>Your searches will be removed from your account and personal insights. Anonymous totals are kept without any link to you.</p>} confirmLabel="Clear history" danger onCancel={() => setConfirm(false)} onConfirm={() => void clear()} />}
    </Section>
  );
}

function PreferencesTab({ user }: { user: User }) {
  const { savePreferences } = useAuth();
  const { setThemePref, setDisplayCurrency } = usePrefs();
  const toast = useToast();
  const [home, setHome] = useState<AirportRef | null>(null);
  useEffect(() => {
    const code = user.preferences.home_airport;
    if (code) api<Airport[]>(`/api/airports/lookup?codes=${code}`).then((r) => setHome(r[0] ? toRef(r[0]) : null)).catch(() => {});
  }, [user.preferences.home_airport]);
  const [p, setP] = useState<Preferences>({ home_airport: null, cabin: null, passengers: null, currency: null, theme: null, ...user.preferences });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await savePreferences(p);
      if (p.theme) setThemePref(p.theme);
      setDisplayCurrency(p.currency ?? null);
      toast('success', 'Preferences saved.');
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return (
    <Section title="Travel preferences" sub="Used to pre-fill searches and display settings on any device you sign in to.">
      <form className="form narrow" onSubmit={submit}>
        <div className="form-field"><span>Home airport</span>
          <AirportField label="Home airport" value={home} onChange={(a) => { setHome(a); setP({ ...p, home_airport: a?.code ?? null }); }} />
          <small>Pre-fills your departure airport when nothing else is selected.</small>
        </div>
        <div className="form-field"><span>Default cabin</span>
          <Listbox label="Default cabin" value={p.cabin ?? 'none'} onChange={(v) => setP({ ...p, cabin: v === 'none' ? null : v as Preferences['cabin'] })}
            options={[{ value: 'none', label: 'No preference' }, ...CABINS.map((c) => ({ value: c, label: c }))]} />
        </div>
        <div className="form-field"><span>Default adults</span>
          <Listbox label="Default adults" value={String(p.passengers ?? 'none')} onChange={(v) => setP({ ...p, passengers: v === 'none' ? null : Number(v) })}
            options={[{ value: 'none', label: 'No preference' }, ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => ({ value: String(n), label: `${n} ${n === 1 ? 'adult' : 'adults'}` }))]} />
        </div>
        <div className="form-field"><span>Display currency</span>
          <Listbox label="Display currency" value={p.currency ?? 'none'} onChange={(v) => setP({ ...p, currency: v === 'none' ? null : v })}
            options={[{ value: 'none', label: 'Original airline currency' }, ...DISPLAY_CURRENCIES.map((c) => ({ value: c, label: c }))]} />
          <small>Converted amounts are approximate (ECB reference rates, other currencies from ExchangeRate-API); the original price is always shown too.</small>
        </div>
        <div className="form-field"><span>Theme</span>
          <Listbox label="Theme" value={p.theme ?? 'none'} onChange={(v) => setP({ ...p, theme: v === 'none' ? null : v as ThemePreference })}
            options={[{ value: 'none', label: "Use this device's setting" }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'System' }]} />
        </div>
        {error && <Notice kind="error">{error}</Notice>}
        <div className="row-actions"><button className="btn btn-primary" disabled={busy}>{busy && <span className="spinner" />}Save preferences</button></div>
      </form>
    </Section>
  );
}

function SecurityTab() {
  const { user, setUser } = useAuth();
  // Accounts created by code sign-in have no password yet and can set one directly.
  const hasPassword = user?.has_password !== false;
  const toast = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirmNext, setConfirmNext] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const change = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (next !== confirmNext) { setError('The new passwords do not match.'); return; }
    setBusy(true);
    try {
      await api('/api/account/password', { method: 'POST', body: { current_password: hasPassword ? current : null, new_password: next } });
      setCurrent(''); setNext(''); setConfirmNext('');
      toast('success', hasPassword ? 'Password changed. Other devices have been signed out.' : 'Password set. You can now also sign in with it.');
      if (!hasPassword) setUser(await api<User>('/api/auth/me'));
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };

  return (
    <>
      <Section title={hasPassword ? 'Change password' : 'Set a password'} sub={hasPassword ? 'Changing your password signs you out on all other devices.' : 'You sign in with emailed codes. Add a password if you also want to sign in with one.'}>
        <form className="form narrow" onSubmit={change}>
          {hasPassword && <label className="form-field"><span>Current password</span><input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" /></label>}
          <label className="form-field"><span>New password</span><input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" /><small>At least 8 characters, including a letter and a number.</small></label>
          <label className="form-field"><span>Confirm new password</span><input type="password" value={confirmNext} onChange={(e) => setConfirmNext(e.target.value)} required autoComplete="new-password" /></label>
          {error && <Notice kind="error">{error}</Notice>}
          <div className="row-actions"><button className="btn btn-primary" disabled={busy}>{busy && <span className="spinner" />}{hasPassword ? 'Change password' : 'Set password'}</button></div>
        </form>
      </Section>
      <Section title="Delete account" sub="Permanently removes your profile, saved flights, favourites, recently viewed flights, preferences and search history.">
        <div className="row-actions"><button className="btn btn-danger" onClick={() => setDeleting(true)}><Trash2 size={15} /> Delete my account</button></div>
      </Section>
      {deleting && <DeleteAccountDialog needsPassword={hasPassword} onClose={() => setDeleting(false)} onDeleted={() => { setUser(null); toast('info', 'Your account has been deleted.'); navigate({ page: 'home' }); window.location.reload(); }} />}
    </>
  );
}

function DeleteAccountDialog({ needsPassword, onClose, onDeleted }: { needsPassword: boolean; onClose: () => void; onDeleted: () => void }) {
  const [password, setPassword] = useState('');
  const [typed, setTyped] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/api/account/delete', { method: 'POST', body: { password: needsPassword ? password : null, confirm: typed } });
      onDeleted();
    } catch (err) { setError(errorText(err)); setBusy(false); }
  };
  return (
    <Modal title="Delete your account?" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Notice kind="warn">This cannot be undone. All of your personal data will be permanently deleted.</Notice>
        {needsPassword && <label className="form-field"><span>Password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></label>}
        <label className="form-field"><span>Type DELETE to confirm</span><input value={typed} onChange={(e) => setTyped(e.target.value)} required autoComplete="off" /></label>
        {error && <Notice kind="error">{error}</Notice>}
        <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-danger" disabled={busy || typed !== 'DELETE' || (needsPassword && !password)}>{busy && <span className="spinner" />}Delete account</button></div>
      </form>
    </Modal>
  );
}
