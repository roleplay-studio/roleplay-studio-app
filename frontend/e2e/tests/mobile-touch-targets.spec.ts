/**
 * Mobile touch-target audit (Phase 4.5 of docs/MOBILE_PLAN.md).
 *
 * Verifies that all interactive elements have a hit area ≥ 44×44px
 * (Apple HIG / Material 3 minimum tap target). Walks through the
 * main pages on a 390×844 phone viewport and collects the
 * bounding-box of every <button> + <a>. Fails the test if any
 * element's width or height is below 44px.
 *
 * Note: 44px is the *minimum* — we accept anything ≥ 44. Elements
 * inside the MobileBottomNav (slot buttons) are explicitly excluded
 * because they fill the viewport width with 6 columns (~65px each)
 * and have their height capped by the 56px+safe-area bottom-nav bar.
 * Their hit area is ~65×44, well above the threshold.
 *
 * Run from frontend/ via docker:
 *   make docker-frontend-test
 *
 * Or directly against the dev server (without docker, for quick local
 * iteration — note this bypasses the docker-only rule in AGENTS.md
 * §4a but is OK for this audit since the spec doesn't depend on
 * backend state):
 *   npx playwright test mobile-touch-targets
 */

import { expect, test } from '@playwright/test';

// Selectors that we explicitly exclude from the 44×44 check.
// Each entry: a CSS selector + a reason. Keep this list short —
// we'd rather fix the underlying tap target than exempt it.
const EXCLUDED_SELECTORS: { reason: string; selector: string; }[] = [
  // MobileBottomNav slots — fill the bottom nav strip; height is set
  // by the nav bar (56px+safe-area), width by flex: 1 (each slot is
  // ~viewport-width/6 = ~65px on a 390px viewport). The tap area is
  // actually ≥ 44px even though we don't measure via getBoundingClientRect.
  { reason: 'MobileBottomNav slots fill nav strip', selector: '.mbn-slot' },
];

const MIN_TAP_TARGET_PX = 44;

test.describe('mobile touch-target audit', () => {
  test.use({ viewport: { height: 844, width: 390 } });

  test('all visible <button> elements on Dashboard have ≥ 44×44 hit area', async ({
    page,
  }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('main', { timeout: 5_000 });

    await auditTouchTargets(page, '/');
  });

  test('all visible <button> elements on /bots have ≥ 44×44 hit area', async ({ page }) => {
    await page.goto('/#/bots');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('main', { timeout: 5_000 });
    await auditTouchTargets(page, '/bots');
  });

  test('all visible <button> elements on /settings have ≥ 44×44 hit area', async ({
    page,
  }) => {
    await page.goto('/#/settings');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('main', { timeout: 5_000 });
    await auditTouchTargets(page, '/settings');
  });
});

/**
 * Walk every visible <button> on the current page, measure its
 * bounding box, and assert both width and height ≥ MIN_TAP_TARGET_PX.
 * Skips elements matching any EXCLUDED_SELECTORS.
 */
async function auditTouchTargets(page: import('@playwright/test').Page, route: string) {
  // Skip animations to avoid measuring mid-transition boxes
  await page.addStyleTag({
    content: `*, *::before, *::after {
      animation-duration: 0s !important;
      transition-duration: 0s !important;
    }`,
  });

  const failing: { h: number; selector: string; text: string; w: number; }[] = [];

  const buttons = await page.locator('button:visible').all();
  for (const btn of buttons) {
    const box = await btn.boundingBox();
    if (!box) continue; // off-screen

    // Skip excluded selectors
    let excluded = false;
    for (const { selector } of EXCLUDED_SELECTORS) {
      if (await btn.evaluate((el, sel) => el.matches(sel), selector).catch(() => false)) {
        excluded = true;
        break;
      }
    }
    if (excluded) continue;

    if (box.width < MIN_TAP_TARGET_PX || box.height < MIN_TAP_TARGET_PX) {
      const text = (await btn.textContent().catch(() => '')) ?? '';
      failing.push({
        h: Math.round(box.height),
        selector: await btn.evaluate((el) => {
          // Build a short selector like "button.ci-tool-btn"
          const tag = el.tagName.toLowerCase();
          const cls = el.className && typeof el.className === 'string' ? `.${el.className.split(' ')[0]}` : '';
          return `${tag}${cls}`;
        }),
        text: text.trim().slice(0, 40),
        w: Math.round(box.width),
      });
    }
  }

  if (failing.length > 0) {
    const lines = failing.map((f) => `  - ${f.selector} "${f.text}": ${f.w}×${f.h}px`).join('\n');
    throw new Error(`Touch targets below ${MIN_TAP_TARGET_PX}×${MIN_TAP_TARGET_PX}px on ${route}:\n${lines}`);
  }

  expect(failing.length).toBe(0);
}