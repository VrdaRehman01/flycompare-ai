import type { ThemePreference } from './types';

export const THEME_KEY = 'fc-theme';
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

export function readThemePreference(storage: StorageLike | null): ThemePreference {
  try {
    const value = storage?.getItem(THEME_KEY);
    if (value === 'light' || value === 'dark' || value === 'system') return value;
  } catch { /* storage blocked */ }
  return 'system';
}

export function writeThemePreference(storage: StorageLike | null, value: ThemePreference): void {
  try { storage?.setItem(THEME_KEY, value); } catch { /* storage blocked */ }
}

export const resolveTheme = (pref: ThemePreference, systemDark: boolean): 'light' | 'dark' =>
  pref === 'system' ? (systemDark ? 'dark' : 'light') : pref;

export const safeLocalStorage = (): Storage | null => {
  try { return window.localStorage; } catch { return null; }
};
