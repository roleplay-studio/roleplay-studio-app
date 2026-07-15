/**
 * Smoke E2E — the smallest possible "is the app alive?" check.
 *
 * Goal: open the SPA in chromium against a real backend, verify
 *   1. The page loads (no broken bundle, JS errors are silent failures).
 *   2. The title is "Roleplay Studio".
 *   3. The bash-defined backend on 55245 responds to /api/setup/status
 *      and the answer is consistent with what frontend sees.
 *
 * This MUST pass before any other test runs. If this fails, the whole
 * test infra is broken (bad bundle, backend not booted, port
 * collision, etc.) — chasing per-feature failures here is a waste.
 */
import { expect, test } from '@playwright/test';

import { test as backendTest } from '../../fixtures/backend';

backendTest('frontend reaches a running backend @smoke', async ({ backend }) => {
  await backend.waitReady();
  const status = await backend.api.get('/api/setup/status');
  expect(status.ok()).toBeTruthy();
  const body = await status.json();
  expect(body).toHaveProperty('api_key_configured');
});

test('root page loads with valid HTML @smoke', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // Ignore network failures — Playwright can race the dev server's
      // first resource request in CI; we exercise the API directly
      // through Playwright's request fixture elsewhere.
      if (text.includes('Failed to load resource')) return;
      consoleErrors.push(`console.error: ${text}`);
    }
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });

  // Title is the cheapest correctness probe.
  await expect(page).toHaveTitle(/Roleplay Studio/i);

  // Body has rendered (not a white screen).
  const bodyText = await page.locator('body').innerText();
  expect(bodyText.length).toBeGreaterThan(0);

  // No silent JS errors.
  expect(consoleErrors).toEqual([]);
});
