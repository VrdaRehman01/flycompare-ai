// Client-side store for destination photo lookups. Photos are found and cached
// by the backend; this batches requests from cards rendered together, shares
// results between cards, and retries lookups the server postponed ("pending").
import type { DestinationImage } from './types';

type Listener = (img: DestinationImage) => void;
type Fetcher = (keys: string[]) => Promise<DestinationImage[]>;

export const BATCH = 24;
export const MAX_RETRIES = 3;
const RETRY_MS = 4000;

export function createImageStore(fetcher: Fetcher, retryMs = RETRY_MS) {
  const cache = new Map<string, DestinationImage>();
  const listeners = new Map<string, Set<Listener>>();
  const attempts = new Map<string, number>();
  const busy = new Set<string>(); // queued or being fetched
  let queue: string[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;

  function publish(row: DestinationImage) {
    cache.set(row.key, row);
    listeners.get(row.key)?.forEach((l) => l(row));
  }

  function settle(row: DestinationImage) {
    busy.delete(row.key);
    if (!row.pending) return publish(row);
    const n = (attempts.get(row.key) ?? 0) + 1;
    attempts.set(row.key, n);
    if (n > MAX_RETRIES) return publish({ key: row.key, available: false });
    publish(row);
    setTimeout(() => request(row.key, true), retryMs * n);
  }

  async function flush() {
    const keys = queue;
    queue = [];
    timer = null;
    for (let i = 0; i < keys.length; i += BATCH) {
      const chunk = keys.slice(i, i + BATCH);
      try {
        const rows = await fetcher(chunk);
        const seen = new Set(rows.map((r) => r.key));
        rows.forEach(settle);
        // Keys the server did not recognise have no photo.
        chunk.filter((k) => !seen.has(k)).forEach((k) => settle({ key: k, available: false }));
      } catch {
        chunk.forEach((k) => settle({ key: k, available: false, pending: true }));
      }
    }
  }

  function request(key: string, retry = false) {
    if (busy.has(key) || (!retry && cache.has(key))) return;
    busy.add(key);
    queue.push(key);
    timer ??= setTimeout(flush, 30);
  }

  return {
    get: (key: string) => cache.get(key),
    request,
    subscribe(key: string, listener: Listener) {
      const set = listeners.get(key) ?? new Set();
      listeners.set(key, set);
      set.add(listener);
      return () => { set.delete(listener); };
    },
  };
}
