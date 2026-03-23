import { afterEach, describe, expect, test, vi } from 'vitest';

vi.stubGlobal('Deno', {
  env: { get: vi.fn() },
  serve: vi.fn(),
});

describe('api proxy contract', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('omits legacy x-poe-session forwarding and cookies', async () => {
    const { buildForwardHeaders, getCorsHeaders } = await import('./contract');

    const corsHeaders = getCorsHeaders(new Request('https://example.test', { method: 'OPTIONS' }));
    expect(corsHeaders['Access-Control-Allow-Headers']).not.toContain('x-poe-session');

    const forwarded = buildForwardHeaders({
      existingCookie: 'foo=bar',
      backendSession: 'session-1',
    });

    expect(forwarded.Cookie).toContain('poe_session=session-1');
    expect(forwarded.Cookie).not.toContain('POESESSID=');
  });
});
