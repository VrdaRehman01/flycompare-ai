/**
 * Links that come from providers or third-party APIs are untrusted: only http(s) URLs
 * may be rendered as links, so a value like "javascript:…" or "data:…" can never run.
 */
export function safeUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value, window.location.origin);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : undefined;
  } catch {
    return undefined;
  }
}
