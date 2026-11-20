import { defineConfig } from '@playwright/test';
import path from 'node:path';

process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.resolve('.playwright-browsers');

const webPort = 5185;

export default defineConfig({
  testDir: './e2e',
  testMatch: 'intake-profile-live-uat.spec.js',
  workers: 1,
  reporter: 'list',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
    url: `http://127.0.0.1:${webPort}`,
    reuseExistingServer: false,
    env: {
      VITE_API_BASE_URL: `http://127.0.0.1:${webPort}`,
      VITE_PROXY_TARGET: 'http://127.0.0.1:5183',
    },
    timeout: 30_000,
  },
});
