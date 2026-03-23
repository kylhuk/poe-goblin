import { expect, test } from '@playwright/test';

test('auth callback relay posts the oauth payload and clears query params', async ({ page }) => {
  await page.route('**/api/v1/auth/callback', async (route) => {
    const request = route.request();
    expect(request.method()).toBe('POST');
    expect(JSON.parse(request.postData() || '{}')).toEqual({
      code: 'code-123',
      state: 'state-456',
      error: null,
      error_description: null,
    });
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'connected' }),
    });
  });

  await page.goto('/auth/callback?code=code-123&state=state-456');

  await expect(page).toHaveURL(/\/auth\/callback$/);
  await expect(page.getByText('Login complete. You can return to the app.')).toBeVisible();
});
