import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api, errorText, setUnauthorizedHandler } from './lib/api';
import { detectLocalCurrency } from './lib/currency';
import { readThemePreference, resolveTheme, safeLocalStorage, writeThemePreference } from './lib/theme';
import type { CodePending, Flight, Preferences, Rates, SavedFlight, SearchForm, ThemePreference, User } from './lib/types';

/* ---------------------------------------------------------------- toasts */

type Toast = { id: number; kind: 'success' | 'error' | 'info'; text: string };
const ToastCtx = createContext<(kind: Toast['kind'], text: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(0);
  const push = useCallback((kind: Toast['kind'], text: string) => {
    const id = ++next.current;
    setToasts((t) => [...t.slice(-2), { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}<button onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))} aria-label="Dismiss">×</button></div>)}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------ preferences */

type PrefsValue = {
  themePref: ThemePreference; theme: 'light' | 'dark'; setThemePref: (t: ThemePreference) => void;
  displayCurrency: string | null; setDisplayCurrency: (c: string | null) => void;
  ratesFor: (base: string) => Rates | null | undefined; // undefined = loading/not requested, null = unavailable
};
const PrefsCtx = createContext<PrefsValue>(null as unknown as PrefsValue);
export const usePrefs = () => useContext(PrefsCtx);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const storage = safeLocalStorage();
  const [themePref, setThemePrefState] = useState<ThemePreference>(() => readThemePreference(storage));
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  // 'none' records an explicit "Original currency" choice; no stored value means the
  // visitor never chose, so prices default to the currency of where they are.
  const [displayCurrency, setDisplayCurrencyState] = useState<string | null>(() => {
    let stored: string | null = null;
    try { stored = storage?.getItem('fc-currency') ?? null; } catch { /* ignore */ }
    if (stored === 'none') return null;
    return stored || detectLocalCurrency();
  });
  const [rates, setRates] = useState<Record<string, Rates | null>>({});
  const requested = useRef(new Set<string>());

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return;
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  const theme = resolveTheme(themePref, systemDark);
  useEffect(() => { document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme; }, [theme]);

  const setThemePref = useCallback((t: ThemePreference) => { setThemePrefState(t); writeThemePreference(safeLocalStorage(), t); }, []);
  const setDisplayCurrency = useCallback((c: string | null) => {
    setDisplayCurrencyState(c);
    try { safeLocalStorage()?.setItem('fc-currency', c ?? 'none'); } catch { /* ignore */ }
  }, []);

  const ratesFor = useCallback((base: string) => {
    if (base in rates) return rates[base];
    if (!requested.current.has(base)) {
      requested.current.add(base);
      api<Rates>(`/api/currency/rates?base=${encodeURIComponent(base)}`)
        .then((r) => setRates((all) => ({ ...all, [base]: r })))
        .catch(() => setRates((all) => ({ ...all, [base]: null })));
    }
    return undefined;
  }, [rates]);

  const value = useMemo(() => ({ themePref, theme, setThemePref, displayCurrency, setDisplayCurrency, ratesFor }), [themePref, theme, setThemePref, displayCurrency, setDisplayCurrency, ratesFor]);
  return <PrefsCtx.Provider value={value}>{children}</PrefsCtx.Provider>;
}

/* ------------------------------------------------------------------ auth */

const LOCAL_FAVS = 'fc-local-favourites';
const LOCAL_SAVED = 'fc-local-saved';
const readLocal = <T,>(key: string): T[] => { try { return JSON.parse(localStorage.getItem(key) ?? '[]') as T[]; } catch { return []; } };
const writeLocal = (key: string, value: unknown[]) => { try { if (value.length) localStorage.setItem(key, JSON.stringify(value)); else localStorage.removeItem(key); } catch { /* storage blocked */ } };

export type AuthPrompt = { mode: 'login' | 'register'; reason?: string; onSuccess?: () => void } | null;
type AuthValue = {
  user: User | null; ready: boolean;
  prompt: AuthPrompt; openAuth: (mode?: 'login' | 'register', reason?: string, onSuccess?: () => void) => void; closeAuth: () => void;
  /** Password sign-in; returns a pending code when the email still has to be verified. */
  login: (email: string, password: string) => Promise<CodePending | null>;
  /** Starts registration: emails a code that creates the account once entered. */
  register: (name: string, email: string, password: string) => Promise<CodePending>;
  requestCode: (email: string) => Promise<CodePending>;
  verifyCode: (email: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
  savePreferences: (p: Preferences) => Promise<void>;
  favourites: string[]; toggleFavourite: (code: string) => Promise<void>;
  saved: SavedFlight[]; isSaved: (offerId: string) => boolean; toggleSaved: (offer: Flight, search: SearchForm | null) => Promise<void>; refreshSaved: () => Promise<void>;
  recordView: (offer: Flight, search: SearchForm | null) => void;
};
const AuthCtx = createContext<AuthValue>(null as unknown as AuthValue);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const { setThemePref, setDisplayCurrency } = usePrefs();
  const [user, setUserState] = useState<User | null>(null);
  const userRef = useRef<User | null>(null);
  userRef.current = user;
  const [ready, setReady] = useState(false);
  const [prompt, setPrompt] = useState<AuthPrompt>(null);
  // Visitors who are not signed in keep favourites and saved flights in this browser.
  const [favourites, setFavourites] = useState<string[]>(() => readLocal<string>(LOCAL_FAVS));
  const [saved, setSaved] = useState<SavedFlight[]>(() => readLocal<SavedFlight>(LOCAL_SAVED));

  const loadPersonal = useCallback(async () => {
    try {
      const [favs, flights] = await Promise.all([api<string[]>('/api/account/favourites'), api<SavedFlight[]>('/api/account/saved-flights')]);
      setFavourites(favs);
      setSaved(flights);
    } catch { /* shown as empty; pages surface their own errors */ }
  }, []);

  /** Move anything saved in this browser into the account, then clear the local copy. */
  const syncLocal = useCallback(async () => {
    const favs = readLocal<string>(LOCAL_FAVS), flights = readLocal<SavedFlight>(LOCAL_SAVED);
    if (!favs.length && !flights.length) return 0;
    let moved = 0;
    for (const code of favs) { try { await api('/api/account/favourites', { method: 'POST', body: { airport_code: code } }); moved++; } catch { /* keep going */ } }
    for (const f of flights) { try { await api('/api/account/saved-flights', { method: 'POST', body: { offer: f.offer, search: f.search } }); moved++; } catch { /* keep going */ } }
    writeLocal(LOCAL_FAVS, []); writeLocal(LOCAL_SAVED, []);
    return moved;
  }, []);

  const applyUser = useCallback((u: User | null, fromSignIn = false) => {
    setUserState(u);
    if (!u) { setFavourites(readLocal<string>(LOCAL_FAVS)); setSaved(readLocal<SavedFlight>(LOCAL_SAVED)); return; }
    void syncLocal().then((n) => { if (n) toast('success', `Moved ${n} item${n === 1 ? '' : 's'} saved in this browser to your account.`); }).finally(() => void loadPersonal());
    // Account preferences follow the user across devices.
    if (fromSignIn && u.preferences.theme) setThemePref(u.preferences.theme);
    if (fromSignIn && u.preferences.currency) setDisplayCurrency(u.preferences.currency);
  }, [loadPersonal, setThemePref, setDisplayCurrency, syncLocal, toast]);

  // A personal request returned 401 while we thought we were signed in: the session expired.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (!userRef.current) return;
      userRef.current = null;
      setUserState(null);
      setFavourites(readLocal<string>(LOCAL_FAVS));
      setSaved(readLocal<SavedFlight>(LOCAL_SAVED));
      toast('info', 'Your session has expired. Please sign in again.');
    });
    return () => setUnauthorizedHandler(null);
  }, [toast]);

  useEffect(() => {
    api<User | null>('/api/auth/me').then((u) => applyUser(u)).catch(() => setUserState(null)).finally(() => setReady(true));
  }, [applyUser]);

  const openAuth = useCallback((mode: 'login' | 'register' = 'login', reason?: string, onSuccess?: () => void) => setPrompt({ mode, reason, onSuccess }), []);
  const closeAuth = useCallback(() => setPrompt(null), []);

  const finishAuth = (u: User, message: string) => {
    applyUser(u, true);
    const after = prompt?.onSuccess;
    setPrompt(null);
    toast('success', message);
    after?.();
  };
  const login = async (email: string, password: string) => {
    const r = await api<User | CodePending>('/api/auth/login', { method: 'POST', body: { email, password } });
    if ('verification_required' in r) return r;
    finishAuth(r, `Welcome back, ${r.name.split(' ')[0]}.`);
    return null;
  };
  const register = (name: string, email: string, password: string) =>
    api<CodePending>('/api/auth/register', { method: 'POST', body: { name, email, password } });
  const requestCode = (email: string) => api<CodePending>('/api/auth/code/request', { method: 'POST', body: { email } });
  const verifyCode = async (email: string, code: string) => {
    const u = await api<User>('/api/auth/code/verify', { method: 'POST', body: { email, code } });
    finishAuth(u, `You're signed in as ${u.email}.`);
  };
  const logout = async () => {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (err) { toast('error', errorText(err)); return; }
    applyUser(null);
    toast('info', 'You have signed out.');
  };
  const savePreferences = async (p: Preferences) => {
    const u = await api<User>('/api/account/preferences', { method: 'PUT', body: p });
    setUserState(u);
  };

  const toggleFavourite = async (code: string) => {
    if (!user) {
      const next = favourites.includes(code) ? favourites.filter((c) => c !== code) : [...favourites, code];
      setFavourites(next);
      writeLocal(LOCAL_FAVS, next);
      if (!favourites.includes(code)) toast('success', 'Saved in this browser. Sign in to keep favourites on all your devices.');
      return;
    }
    const isFav = favourites.includes(code);
    try {
      const next = await api<string[]>(isFav ? `/api/account/favourites/${code}` : '/api/account/favourites', isFav ? { method: 'DELETE' } : { method: 'POST', body: { airport_code: code } });
      setFavourites(next);
    } catch (err) { toast('error', errorText(err)); }
  };

  const refreshSaved = useCallback(async () => {
    if (!user) { setSaved(readLocal<SavedFlight>(LOCAL_SAVED)); return; }
    try { setSaved(await api<SavedFlight[]>('/api/account/saved-flights')); } catch (err) { toast('error', errorText(err)); }
  }, [toast, user]);
  const isSaved = (offerId: string) => saved.some((s) => s.offer_id === offerId);
  const toggleSaved = async (offer: Flight, search: SearchForm | null) => {
    const existing = saved.find((s) => s.offer_id === offer.id);
    if (!user) {
      const next = existing ? saved.filter((s) => s.offer_id !== offer.id)
        : [{ id: -Date.now(), offer_id: offer.id, offer, search, saved_at: new Date().toISOString() }, ...saved].slice(0, 50);
      setSaved(next);
      writeLocal(LOCAL_SAVED, next);
      toast(existing ? 'info' : 'success', existing ? 'Removed from saved flights.' : 'Saved in this browser. Sign in to keep saved flights on all your devices.');
      return;
    }
    try {
      if (existing) {
        await api(`/api/account/saved-flights/${existing.id}`, { method: 'DELETE' });
        setSaved((all) => all.filter((s) => s.id !== existing.id));
        toast('info', 'Removed from saved flights.');
      } else {
        const row = await api<SavedFlight>('/api/account/saved-flights', { method: 'POST', body: { offer, search } });
        setSaved((all) => [row, ...all.filter((s) => s.id !== row.id)]);
        toast('success', 'Saved. Find it under Account → Saved flights.');
      }
    } catch (err) { toast('error', errorText(err)); }
  };
  const recordView = (offer: Flight, search: SearchForm | null) => {
    if (user) void api('/api/account/recently-viewed', { method: 'POST', body: { offer, search } }).catch(() => {});
  };

  const value: AuthValue = {
    user, ready, prompt, openAuth, closeAuth, login, register, requestCode, verifyCode, logout, setUser: setUserState, savePreferences,
    favourites, toggleFavourite, saved, isSaved, toggleSaved, refreshSaved, recordView,
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
