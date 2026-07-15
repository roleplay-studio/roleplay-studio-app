/**
 * Playwright config — E2E for Roleplay Studio.
 *
 * Strategy: spawn the actual FastAPI backend on 127.0.0.1:55245 (via
 * `uv run python backend/run_backend.py`) and the vite dev server on
 * 127.0.0.1:5173. Tests run against those real processes — no mocks,
 * no MSW. The LLM (Deepseek) is hit for real because the spec was
 * "honest E2E". Per-test data isolation is achieved by giving each test
 * a fresh `e2e_tmp/<project-hash>/` data dir with its own `.env`,
 * sqlite db, chroma dir, uploads dir.
 *
 * Multi-viewport: web project ships with `responsive` design (mobile,
 * laptop, desktop). Three viewports = three projects = real coverage.
 * Critical journeys run on chromium only; webkit/firefox only for the
 * smoke set.
 */
import { defineConfig, devices } from '@playwright/test';

const FRONTEND_PORT = 5173;

export default defineConfig({
  expect: { timeout: 5_000 },
  forbidOnly: !!process.env.CI,
  fullyParallel: true,
  projects: [
    {
      name: 'critical-chromium',
      testMatch: /critical\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'desktop-chromium',
      testMatch: /pages\/.*\.desktop\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { height: 900, width: 1440 } },
    },
    {
      name: 'laptop-chromium',
      testMatch: /pages\/.*\.laptop\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { height: 768, width: 1024 } },
    },
    {
      name: 'mobile-chromium',
      testMatch: /pages\/.*\.mobile\.spec\.ts/,
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'integration-chromium',
      testMatch: /integration\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'visual-chromium',
      testMatch: /visual\/.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['list']]
    : [['list'], ['html', { open: 'never' }]],
  retries: process.env.CI ? 1 : 0,

  testDir: './e2e/tests',
  // 30 s budget — Deepseek average first-token is <2 s but cold start
  // and Chroma indexing push beyond typical 5 s.
  timeout: 30_000,

  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    // actionTimeout: 8_000,  // enabled if flake shows up

    // Fail fast on console errors so we don't ship silent JS breakage.
    // ApplicationError events are logged through a custom transport,
    // so console.error is the canonical signal we can listen for.
  },

  // The backend (FastAPI on 55245) is started by hand before the suite
  // runs (`make e2e-backend`). Playwright's `webServer` only manages the
  // frontend, so a stale dev-server can be reused with
  // `reuseExistingServer: !CI`. CI must NOT rely on an external process.
  webServer: [
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      reuseExistingServer: !process.env.CI,
      stderr: 'pipe',
      stdout: 'ignore',
      timeout: 60_000,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
    },
  ],

  workers: process.env.CI ? 1 : undefined,
});
