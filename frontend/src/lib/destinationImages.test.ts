import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createImageStore, MAX_RETRIES } from './destinationImages';
import type { DestinationImage } from './types';

const ok = (key: string): DestinationImage => ({ key, available: true, url: `https://upload.wikimedia.org/${key}.jpg`, licence: 'CC0', artist: 'A' });

describe('destination image store', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('batches keys requested together and shares results', async () => {
    const fetcher = vi.fn(async (keys: string[]) => keys.map(ok));
    const store = createImageStore(fetcher);
    const seen: DestinationImage[] = [];
    store.subscribe('Paris|FR', (r) => seen.push(r));
    store.request('Paris|FR');
    store.request('Dubai|AE');
    store.request('Paris|FR');
    await vi.advanceTimersByTimeAsync(50);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toEqual(['Paris|FR', 'Dubai|AE']);
    expect(seen.map((r) => r.available)).toEqual([true]);
    store.request('Paris|FR'); // cached
    await vi.advanceTimersByTimeAsync(50);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('splits large batches to the API limit', async () => {
    const fetcher = vi.fn(async (keys: string[]) => keys.map(ok));
    const store = createImageStore(fetcher);
    for (let i = 0; i < 30; i++) store.request(`City${i}|XX`);
    await vi.advanceTimersByTimeAsync(50);
    expect(fetcher.mock.calls.map((c) => c[0].length)).toEqual([24, 6]);
  });

  it('retries pending lookups and then gives up with the fallback', async () => {
    const fetcher = vi.fn(async (keys: string[]) => keys.map((key) => ({ key, available: false, pending: true })));
    const store = createImageStore(fetcher, 100);
    store.request('Lahore|PK');
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetcher).toHaveBeenCalledTimes(MAX_RETRIES + 1);
    expect(store.get('Lahore|PK')).toEqual({ key: 'Lahore|PK', available: false });
  });

  it('a pending lookup that later succeeds updates subscribers', async () => {
    let calls = 0;
    const store = createImageStore(async (keys) => keys.map((key) => (++calls === 1 ? { key, available: false, pending: true } : ok(key))), 100);
    const seen: boolean[] = [];
    store.subscribe('Lahore|PK', (r) => seen.push(r.available));
    store.request('Lahore|PK');
    await vi.advanceTimersByTimeAsync(1000);
    expect(seen).toEqual([false, true]);
  });

  it('network errors are treated as pending, not as "no photo"', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue([ok('Rome|IT')]);
    const store = createImageStore(fetcher, 100);
    store.request('Rome|IT');
    await vi.advanceTimersByTimeAsync(1000);
    expect(store.get('Rome|IT')?.available).toBe(true);
  });

  it('keys the server ignores resolve to no photo', async () => {
    const store = createImageStore(async () => []);
    store.request('Nowhere|XX');
    await vi.advanceTimersByTimeAsync(50);
    expect(store.get('Nowhere|XX')).toEqual({ key: 'Nowhere|XX', available: false });
  });
});
