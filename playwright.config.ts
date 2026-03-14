import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './src/test/playwright',
  timeout: 30_000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
  },
  webServer: {
    command: 'npm run qa:dev',
    port: 4173,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
