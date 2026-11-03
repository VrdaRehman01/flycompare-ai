import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// vercel.json (production) and security-headers.json (local preview) must not drift apart.
const read = (name: string) => JSON.parse(readFileSync(new URL(`../../${name}`, import.meta.url), 'utf8'));

describe('security headers', () => {
  it('match between Vercel and the local preview', () => {
    const { _comment, ...local } = read('security-headers.json') as Record<string, string>;
    void _comment;
    const vercel = read('vercel.json') as { headers: { source: string; headers: { key: string; value: string }[] }[] };
    const all = Object.fromEntries(vercel.headers.find((h) => h.source === '/(.*)')!.headers.map((h) => [h.key, h.value]));
    expect(all).toEqual(local);
  });
  it('allow scripts only from the site itself and forbid framing', () => {
    const csp = (read('security-headers.json') as Record<string, string>)['Content-Security-Policy'];
    expect(csp).toContain("script-src 'self';");
    expect(csp).not.toMatch(/script-src[^;]*unsafe/);
    expect(csp).toContain("frame-ancestors 'none'");
  });
});
