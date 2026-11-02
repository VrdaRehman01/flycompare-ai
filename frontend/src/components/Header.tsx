import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { BarChart3, BookOpen, Bookmark, CarFront, Check, ChevronDown, Globe2, Heart, History, KeyRound, LogIn, LogOut, Mail, Menu, Monitor, Moon, Plane, Settings, Sun, User as UserIcon, UserPlus, UserRound, Users, Wand2, X } from 'lucide-react';
import { errorText } from '../lib/api';
import { useFeatures, type DemoService } from '../lib/features';
import { navigate, type Route } from '../lib/router';
import type { CodePending, ThemePreference } from '../lib/types';
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

type AuthView = 'code' | 'password' | 'register' | 'enter';
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * Sign in by emailed code (default) or password, or create an account with a password.
 * Every route that needs the email confirmed ends on the code entry step.
 */
export function AuthModal() {
  const { prompt, closeAuth, login, register, requestCode, verifyCode } = useAuth();
  const [view, setView] = useState<AuthView>('code');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [pending, setPending] = useState<CodePending | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!prompt) return;
    setView(prompt.mode === 'register' ? 'register' : 'code');
    setError(''); setPassword(''); setCode(''); setPending(null);
  }, [prompt?.mode, prompt]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);
  if (!prompt) return null;

  const go = (v: AuthView) => { setView(v); setError(''); };
  const run = async (task: () => Promise<void>) => {
    setError(''); setBusy(true);
    try { await task(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  const awaitCode = (p: CodePending) => { setPending(p); setCode(''); setCooldown(p.resend_after_seconds); setView('enter'); };
  const checkEmail = () => { if (!EMAIL_RE.test(email.trim())) { setError('Enter a valid email address.'); return false; } return true; };

  const sendCode = (e?: FormEvent) => { e?.preventDefault(); if (checkEmail()) void run(async () => awaitCode(await requestCode(email.trim()))); };
  const signIn = (e: FormEvent) => {
    e.preventDefault();
    if (checkEmail()) void run(async () => { const p = await login(email.trim(), password); if (p) awaitCode(p); });
  };
  const create = (e: FormEvent) => {
    e.preventDefault();
    if (!checkEmail()) return;
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) { setError('Use at least 8 characters with at least one letter and one number.'); return; }
    void run(async () => awaitCode(await register(name, email.trim(), password)));
  };
  const confirm = (value = code) => {
    if (!/^\d{6}$/.test(value) || !pending) { setError('Enter the 6-digit code from the email.'); return; }
    void run(async () => { await verifyCode(pending.email, value); });
  };
  const resend = () => void run(async () => {
    const p = view === 'enter' && pending && password && name ? await register(name, pending.email, password) : await requestCode(pending?.email ?? email.trim());
    awaitCode(p);
  });

  const titles: Record<AuthView, string> = { code: 'Sign in or create an account', password: 'Sign in with password', register: 'Create your account', enter: 'Check your email' };
  const emailField = <label className="form-field"><span>Email</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required maxLength={254} autoFocus /></label>;
  const submitBtn = (label: string) => <button className="btn btn-primary full" disabled={busy}>{busy && <span className="spinner" />}{label}</button>;

  return (
    <Modal title={titles[view]} onClose={closeAuth}>
      {prompt.reason && view !== 'enter' && <Notice>{prompt.reason}</Notice>}

      {view === 'code' && (
        <form className="form" onSubmit={sendCode} noValidate>
          {emailField}
          <p className="auth-hint"><Mail size={14} /> We'll email you a 6-digit code. New here? The code creates your account.</p>
          {error && <Notice kind="error">{error}</Notice>}
          {submitBtn('Email me a code')}
          <div className="auth-alt"><span>or</span></div>
          <button type="button" className="btn btn-ghost full" onClick={() => go('password')}><KeyRound size={15} /> Sign in with a password</button>
        </form>
      )}

      {view === 'password' && (
        <form className="form" onSubmit={signIn} noValidate>
          {emailField}
          <label className="form-field"><span>Password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required maxLength={128} /></label>
          {error && <Notice kind="error">{error}</Notice>}
          {submitBtn('Sign in')}
          <p className="auth-links"><button type="button" className="link-btn" onClick={() => go('code')}>Forgot password? Sign in with a code</button></p>
        </form>
      )}

      {view === 'register' && (
        <form className="form" onSubmit={create} noValidate>
          <label className="form-field"><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required maxLength={100} autoFocus /></label>
          {emailField}
          <label className="form-field"><span>Password</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required maxLength={128} />
            <small>At least 8 characters, including a letter and a number.</small></label>
          {error && <Notice kind="error">{error}</Notice>}
          {submitBtn('Create account')}
          <p className="auth-hint"><Mail size={14} /> We'll email a code to confirm the address before the account is created.</p>
        </form>
      )}

      {view === 'enter' && pending && (
        <form className="form" onSubmit={(e) => { e.preventDefault(); confirm(); }} noValidate>
          <p className="auth-sent"><Mail size={18} /> <span>We sent a 6-digit code to <b>{pending.email}</b>. It expires in {Math.round(pending.expires_in_seconds / 60)} minutes.</span></p>
          <label className="form-field"><span>Code</span>
            <input className="code-input" value={code} inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="••••••" autoFocus aria-label="6-digit code"
              onChange={(e) => { const v = e.target.value.replace(/\D/g, '').slice(0, 6); setCode(v); if (v.length === 6) confirm(v); }} />
          </label>
          {error && <Notice kind="error">{error}</Notice>}
          {submitBtn('Verify and continue')}
          <p className="auth-links">
            <button type="button" className="link-btn" disabled={cooldown > 0 || busy} onClick={resend}>{cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}</button>
            <button type="button" className="link-btn" onClick={() => { setPending(null); go('code'); }}>Use a different email</button>
          </p>
          <p className="modal-fine">Can't find it? Check your spam or promotions folder.</p>
        </form>
      )}

      {view !== 'enter' && (
        <p className="modal-switch">
          {view === 'register' ? 'Already have an account? ' : 'New to FlyCompare? '}
          <button className="link-btn" onClick={() => go(view === 'register' ? 'code' : 'register')}>{view === 'register' ? 'Sign in' : 'Create an account with a password'}</button>
        </p>
      )}
      <p className="modal-fine">Codes expire after a few minutes and work once. Passwords are stored as salted scrypt hashes; your session uses a secure HttpOnly cookie.</p>
    </Modal>
  );
}
