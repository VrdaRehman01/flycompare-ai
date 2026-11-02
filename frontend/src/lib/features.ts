import { useEffect, useState } from 'react';
import { api } from './api';

/** Services with only simulated inventory; the API lists them in /api/meta only when enabled. */
export type DemoService = 'stays' | 'cars' | 'transfers' | 'tours' | 'packages';

let request: Promise<Set<string>> | null = null;
const load = () => (request ??= api<{ features: string[] }>('/api/meta')
  .then((m) => new Set(m.features))
  .catch(() => { request = null; return new Set<string>(); }));

/** Features the API server offers, or null while the answer is still loading. */
export function useFeatureState(): Set<string> | null {
  const [features, setFeatures] = useState<Set<string> | null>(null);
  useEffect(() => {
    let live = true;
    void load().then((f) => { if (live) setFeatures(f); });
    return () => { live = false; };
  }, []);
  return features;
}

/**
 * Features the API server offers. Until it answers, nothing optional is shown, so a
 * hidden service never flashes into the navigation.
 */
export function useFeatures(): Set<string> {
  return useFeatureState() ?? EMPTY;
}
const EMPTY: Set<string> = new Set();
