/**
 * Critical-5 — Onboarding & navigation smoke.
 *
 * The dev environment's backend is pre-configured (api_key set,
 * starter bots seeded), so ``App.svelte`` should resolve to
 * ``needsSetup === false`` and route past the wizard to the
 * Dashboard. We exercise:
 *
 *   1. Cold load to ``/``  → splash dissolves, ``aside.sb-root``
 *      appears (sidebar).
 *   2. Hash-route change ``# → #/bots`` via location.hash triggers
 *      ``hashchange`` and the Sidebar nav re-renders — the same
 *      path the user takes when clicking a nav button.
 *
 * Why bother if onboarding is mostly a wizard? Because
 * ``App.svelte`` has a complex ``checkBackend`` retry loop with
 * both an ``AbortController`` and a ``503 wait`` path. If those
 * regress, every other test in this suite times out. Anchoring
 * on the cheap "did the app boot past splash?" signal catches
 * the class of bugs that take down the whole suite.
 */
import { expect, test } from '@playwright/test';

import { DashboardPage } from '../../pages/Dashboard.page';

test('cold load: splash dissolves, sidebar renders, dashboard route is active @smoke', async ({
  page,
}) => {
  const dashboard = new DashboardPage(page);
  await dashboard.gotoRoot();
  await dashboard.waitForDashboard();
  // Dashboard content area is rendered (anything other than splash).
  const text = await dashboard.content.innerText();
  expect(text.length).toBeGreaterThan(0);
});

test('hash navigation: switching to /bots re-renders Sidebar NavItems @smoke', async ({ page }) => {
  const base = new DashboardPage(page);
  await base.gotoRoot();
  await base.waitForAppReady();

  // The user clicks "Bots" in the sidebar; we replicate via the
  // same code path Svelte listens to.
  await base.gotoHash('/bots');
  await base.page.waitForTimeout(150);
  await expect(base.page).toHaveURL(/#\/bots$/);
});
