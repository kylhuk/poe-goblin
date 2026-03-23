import { expect, test } from '@playwright/test';

test('auth callback relay calls the proxy callback endpoint and clears query params', async ({ page }) => {
  await page.route('**/functions/v1/api-proxy', async (route) => {
    const request = route.request();
    expect(request.method()).toBe('GET');
    expect(request.headers()['x-proxy-path']).toBe('/api/v1/auth/callback?code=code-123&state=state-456');

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'connected' }),
    });
  });

  await page.goto('/auth/callback?code=code-123&state=state-456');

  await expect(page).toHaveURL(/\/auth\/callback$/);
  await expect(page.getByText('Path of Exile connected. Closing window…')).toBeVisible();
});

