// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';

import AuthCallback from './AuthCallback';

const { refreshSessionMock, authProxyFetchMock } = vi.hoisted(() => ({
  refreshSessionMock: vi.fn(),
  authProxyFetchMock: vi.fn(),
}));

vi.mock('@/services/auth', () => ({
  useAuth: () => ({
    refreshSession: refreshSessionMock,
  }),
}));

vi.mock('@/services/authProxy', () => ({
  POE_OAUTH_MESSAGE: 'poe-oauth-result',
  authProxyFetch: authProxyFetchMock,
  persistOAuthRelayResult: vi.fn(),
}));

beforeEach(() => {
  refreshSessionMock.mockReset();
  authProxyFetchMock.mockReset();
  vi.spyOn(window, 'close').mockImplementation(() => undefined);
});

test('keeps the callback page open when the session is not confirmed', async () => {
  authProxyFetchMock.mockResolvedValue(
    new Response(JSON.stringify({ status: 'connected' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  refreshSessionMock.mockResolvedValue({ status: 'disconnected' });

  window.history.pushState({}, '', '/auth/callback?code=code-123&state=state-456');

  render(
    <MemoryRouter initialEntries={['/auth/callback?code=code-123&state=state-456']}>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallback />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => {
    expect(screen.getByText('Path of Exile session was not confirmed')).toBeInTheDocument();
  }, { timeout: 3000 });
  expect(window.close).not.toHaveBeenCalled();
});
