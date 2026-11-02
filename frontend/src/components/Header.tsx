import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { BarChart3, BookOpen, Bookmark, CarFront, Check, ChevronDown, Globe2, Heart, History, LogIn, LogOut, Menu, Monitor, Moon, Plane, Settings, Sun, User as UserIcon, UserPlus, UserRound, Users, Wand2, X } from 'lucide-react';
import { errorText } from '../lib/api';
import { useFeatures, type DemoService } from '../lib/features';
import { navigate, type Route } from '../lib/router';
import type { ThemePreference } from '../lib/types';
import { useAuth, usePrefs } from '../state';
import { Modal, Notice } from './ui';

// Currencies published in the ECB reference rates (the conversion source).
export const DISPLAY_CURRENCIES = [
  'USD', 'EUR', 'GBP', 'PKR', 'AED', 'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'INR', 'BDT', 'LKR', 'NPR', 'TRY', 'EGP',
  'CHF', 'CAD', 'AUD', 'NZD', 'JPY', 'CNY', 'HKD', 'SGD', 'MYR', 'THB', 'IDR', 'PHP', 'KRW', 'SEK', 'NOK', 'DKK', 'PLN', 'ZAR', 'BRL', 'MXN',
];

export function Dropdown({ button, label, children, align = 'right', className = '' }: { button: ReactNode; label: string; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; className?: string }) {
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
  return (
    <div className={`dropdown ${className}`} ref={ref}>
      <button className="dropdown-trigger" aria-haspopup="menu" aria-expanded={open} aria-label={label} onClick={() => setOpen((v) => !v)}>{button}</button>
      {open && <div className={`dropdown-menu card align-${align}`} role="menu">{children(() => setOpen(false))}</div>}
    </div>
  );
}

export function Header({ route }: { route: Route }) {
  const { user, openAuth, logout } = useAuth();
  const { themePref, theme, setThemePref, displayCurrency, setDisplayCurrency } = usePrefs();
  const [mobileNav, setMobileNav] = useState(false);
  const active = route.page === 'results' || route.page === 'details' ? 'home' : route.page;
  const go = (r: Route) => { setMobileNav(false); navigate(r); };
  // Services with only simulated inventory appear only when the API enables them.
  const features = useFeatures();
  const offered = <T extends { needs?: DemoService }>(items: T[]) => items.filter((i) => !i.needs || features.has(i.needs));
  const travelServices = features.has('stays');
  const nav = offered<{ route: Route; label: string; key: string; needs?: DemoService }>([
    { route: { page: 'home' }, label: 'Flights', key: 'home' }, { route: { page: 'stays' }, label: 'Hotels & Homes', key: 'stays', needs: 'stays' },
    { route: { page: 'packages' }, label: 'Flight & Hotel', key: 'packages', needs: 'packages' }, { route: { page: 'cars', tab: 'rental' }, label: 'Cars', key: 'cars', needs: 'cars' },
    { route: { page: 'tours', kind: 'group' }, label: 'Tours', key: 'tours', needs: 'tours' }, { route: { page: 'deals' }, label: 'Deals', key: 'deals' },
    { route: { page: 'destinations' }, label: 'Destinations', key: 'destinations' },
    // With the travel services hidden there is room for Insights in the main bar again.
    ...(travelServices ? [] : [{ route: { page: 'insights' } as Route, label: 'Insights', key: 'insights' }]),
  ]);
  const more = offered<{ route: Route; label: string; hint: string; icon: ReactNode; key: string; needs?: DemoService }>([
    { route: { page: 'planner' }, label: 'Trip planner', hint: 'Day-by-day itinerary and budget', icon: <Wand2 size={15} />, key: 'planner' },
    { route: { page: 'guides' }, label: 'Travel guides', hint: 'Sights, areas and best months', icon: <BookOpen size={15} />, key: 'guides' },
    { route: { page: 'tours', kind: 'group' }, label: 'Group tours', hint: 'Shared guided tours', icon: <Users size={15} />, key: 'tours-group', needs: 'tours' },
    { route: { page: 'tours', kind: 'private' }, label: 'Private tours', hint: 'Your own guide and car', icon: <UserRound size={15} />, key: 'tours-private', needs: 'tours' },
    { route: { page: 'cars', tab: 'transfers' }, label: 'Airport transfers', hint: 'Airport ↔ city rides', icon: <CarFront size={15} />, key: 'transfers', needs: 'transfers' },
    ...(travelServices ? [{ route: { page: 'insights' } as Route, label: 'Insights', hint: 'Search and fare analytics', icon: <BarChart3 size={15} />, key: 'insights' }] : []),
  ]);
  const moreActive = active === 'planner' || active === 'guides' || (travelServices && active === 'insights');
  const themeIcon = themePref === 'system' ? <Monitor size={16} /> : theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />;
  const themes: { value: ThemePreference; label: string; icon: ReactNode }[] = [
    { value: 'light', label: 'Light', icon: <Sun size={15} /> }, { value: 'dark', label: 'Dark', icon: <Moon size={15} /> }, { value: 'system', label: 'System', icon: <Monitor size={15} /> },
  ];

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <a className="brand" href="#/" onClick={() => setMobileNav(false)} aria-label="FlyCompare AI home">
          <span className="brand-mark"><Plane size={18} /></span>
          <span>FlyCompare <b>AI</b></span>
        </a>
        <nav className={`main-nav ${mobileNav ? 'open' : ''}`} aria-label="Main">
          {nav.map((n) => <button key={n.key} className={active === n.key ? 'active' : ''} aria-current={active === n.key ? 'page' : undefined} onClick={() => go(n.route)}>{n.label}</button>)}
          <Dropdown label="More travel services" align="left" className={`nav-more ${moreActive ? 'active' : ''}`} button={<span className="nav-more-btn">More <ChevronDown size={14} /></span>}>
            {(close) => more.map((m) => (
              <button key={m.key} role="menuitem" className="menu-item rich" onClick={() => { close(); go(m.route); }}>
                {m.icon}<span><b>{m.label}</b><small>{m.hint}</small></span>
              </button>
            ))}
          </Dropdown>
          {/* In the collapsed (mobile) menu the "More" items are listed inline instead. */}
          {more.filter((m) => !m.key.startsWith('tours-')).map((m) => <button key={m.key} className={`nav-flat ${active === m.key ? 'active' : ''}`} onClick={() => go(m.route)}>{m.label}</button>)}
        </nav>
        <div className="header-actions">
          <Dropdown label="Display currency" className="currency-dd" button={<span className="currency-pill"><Globe2 size={14} />{displayCurrency ?? 'Original'}<ChevronDown size={13} /></span>}>
            {(close) => (
              <div className="menu-scroll">
                <p className="menu-note">Prices are quoted by the airline. Conversions use ECB reference rates (other currencies from ExchangeRate-API) and are approximate. Defaults to your location's currency.</p>
                <MenuItem active={!displayCurrency} onClick={() => { setDisplayCurrency(null); close(); }}>Original currency</MenuItem>
                {DISPLAY_CURRENCIES.map((c) => <MenuItem key={c} active={displayCurrency === c} onClick={() => { setDisplayCurrency(c); close(); }}>{c}</MenuItem>)}
              </div>
            )}
          </Dropdown>
          <Dropdown label={`Theme: ${themePref}`} button={<span className="icon-btn">{themeIcon}</span>}>
            {(close) => themes.map((t) => <MenuItem key={t.value} icon={t.icon} active={themePref === t.value} onClick={() => { setThemePref(t.value); close(); }}>{t.label}</MenuItem>)}
          </Dropdown>
          {user ? (
            <Dropdown label="Account menu" button={<span className="avatar signed-in" title={user.name}>{initials(user.name)}</span>}>
              {(close) => (
                <>
                  <div className="menu-user"><b>{user.name}</b><small>{user.email}</small></div>
                  <MenuItem icon={<UserIcon size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'profile' }); }}>My account</MenuItem>
                  <MenuItem icon={<Bookmark size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'saved' }); }}>Saved flights</MenuItem>
                  <MenuItem icon={<Heart size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'favourites' }); }}>Favourite destinations</MenuItem>
                  <MenuItem icon={<History size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'history' }); }}>Search history</MenuItem>
                  <MenuItem icon={<BarChart3 size={15} />} onClick={() => { close(); go({ page: 'insights' }); }}>My insights</MenuItem>
                  <MenuItem icon={<Settings size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'preferences' }); }}>Preferences</MenuItem>
                  <div className="menu-sep" />
                  <MenuItem icon={<LogOut size={15} />} onClick={() => { close(); void logout(); }}>Sign out</MenuItem>
                </>
              )}
            </Dropdown>
          ) : (
            <Dropdown label="Account menu" button={<span className="avatar"><UserIcon size={16} /></span>}>
              {(close) => (
                <>
                  <p className="menu-note">Everything works without an account. Sign in to sync saved flights, favourites and history across devices.</p>
                  <MenuItem icon={<LogIn size={15} />} onClick={() => { close(); openAuth('login'); }}>Sign in</MenuItem>
                  <MenuItem icon={<UserPlus size={15} />} onClick={() => { close(); openAuth('register'); }}>Create account</MenuItem>
                  <div className="menu-sep" />
                  <MenuItem icon={<Bookmark size={15} />} onClick={() => { close(); go({ page: 'account', tab: 'saved' }); }}>Saved in this browser</MenuItem>
                  <MenuItem icon={<BarChart3 size={15} />} onClick={() => { close(); go({ page: 'insights' }); }}>Public insights</MenuItem>
                </>
              )}
            </Dropdown>
          )}
          <button className="mobile-menu" onClick={() => setMobileNav((v) => !v)} aria-label="Menu" aria-expanded={mobileNav}>{mobileNav ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
      </div>
    </header>
  );
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

export function MenuItem({ children, onClick, icon, active }: { children: ReactNode; onClick: () => void; icon?: ReactNode; active?: boolean }) {
  return <button role="menuitem" className={`menu-item ${active ? 'active' : ''}`} onClick={onClick}>{icon}<span>{children}</span>{active && <Check size={14} className="menu-check" />}</button>;
}

export function AuthModal() {
  const { prompt, closeAuth, login, register, openAuth } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setError(''); setPassword(''); }, [prompt?.mode]);
  if (!prompt) return null;
  const isRegister = prompt.mode === 'register';

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (isRegister && (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password))) {
      setError('Use at least 8 characters with at least one letter and one number.');
      return;
    }
    setBusy(true);
    try {
      if (isRegister) await register(name, email, password); else await login(email, password);
      setName(''); setEmail(''); setPassword('');
    } catch (err) {
      setError(errorText(err));
    } finally { setBusy(false); }
  };

  return (
    <Modal title={isRegister ? 'Create your account' : 'Sign in'} onClose={closeAuth}>
      {prompt.reason && <Notice>{prompt.reason}</Notice>}
      <form className="form" onSubmit={submit}>
        {isRegister && <label className="form-field"><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required maxLength={100} /></label>}
        <label className="form-field"><span>Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required maxLength={254} /></label>
        <label className="form-field"><span>Password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={isRegister ? 'new-password' : 'current-password'} required maxLength={128} />
          {isRegister && <small>At least 8 characters, including a letter and a number.</small>}</label>
        {error && <Notice kind="error">{error}</Notice>}
        <button className="btn btn-primary full" disabled={busy}>{busy && <span className="spinner" />}{isRegister ? 'Create account' : 'Sign in'}</button>
      </form>
      <p className="modal-switch">
        {isRegister ? 'Already have an account? ' : 'New to FlyCompare? '}
        <button className="link-btn" onClick={() => openAuth(isRegister ? 'login' : 'register', prompt.reason, prompt.onSuccess)}>{isRegister ? 'Sign in' : 'Create an account'}</button>
      </p>
      <p className="modal-fine">Passwords are stored as salted scrypt hashes. Your session uses a secure HttpOnly cookie.</p>
    </Modal>
  );
}
