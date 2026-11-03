import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { safeUrl } from './safeUrl';

// Vitest runs in Node: give safeUrl the browser origin it resolves relative links against.
const g = globalThis as unknown as { window?: { location: { origin: string } } };
const previous = g.window;
beforeAll(() => { g.window = { location: { origin: 'https://flycompare.example' } }; });
afterAll(() => { g.window = previous; });

describe('safeUrl', () => {
  it('keeps http and https links', () => {
    expect(safeUrl('https://www.aviasales.com/search/x?marker=1')).toBe('https://www.aviasales.com/search/x?marker=1');
    expect(safeUrl('http://example.com/a')).toBe('http://example.com/a');
  });
  it('drops script and data links', () => {
    expect(safeUrl('javascript:alert(1)')).toBeUndefined();
    expect(safeUrl(' JaVaScRiPt:alert(1)')).toBeUndefined();
    expect(safeUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined();
    expect(safeUrl('vbscript:msgbox(1)')).toBeUndefined();
  });
  it('treats empty values as no link', () => {
    expect(safeUrl(null)).toBeUndefined();
    expect(safeUrl('')).toBeUndefined();
  });
});
