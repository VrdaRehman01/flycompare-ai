// Thin client for the FastAPI backend. Sessions use an HttpOnly cookie set by
// the server; the browser never sees a token or any provider credentials.

const API = import.meta.env.VITE_API_BASE_URL ?? '';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function messageFrom(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: surface the first readable message.
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const msg = (first.msg ?? 'Invalid input').replace(/^Value error, /, '');
    return msg;
  }
  if (status === 429) return 'Too many requests. Please wait a moment and try again.';
  if (status >= 500) return 'The server could not complete this request. Please try again.';
  return 'Request failed.';
}

let onUnauthorized: (() => void) | null = null;
/** Called when a personal endpoint reports the session is no longer valid. */
export const setUnauthorizedHandler = (fn: (() => void) | null) => { onUnauthorized = fn; };

export async function api<T>(path: string, init: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method: init.method ?? 'GET',
      credentials: 'include',
      signal: init.signal,
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'FlyCompare',
        ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError('Could not reach the FlyCompare server. Check that the backend is running.', 0);
  }
  if (response.status === 204) return undefined as T;
  let body: unknown = null;
  try { body = await response.json(); } catch { /* empty or non-JSON body */ }
  if (!response.ok) {
    if (response.status === 401 && path.startsWith('/api/account')) onUnauthorized?.();
    if (response.status === 404 && (body as { detail?: unknown } | null)?.detail === 'Not Found') {
      // FastAPI's default 404 for an unknown route: the API server is missing this feature.
      throw new ApiError('This feature is not available on the API server. It may be running an older version — restart the backend.', 404);
    }
    throw new ApiError(messageFrom(body, response.status), response.status);
  }
  return body as T;
}

export const errorText = (err: unknown) => err instanceof Error ? err.message : 'Something went wrong.';
