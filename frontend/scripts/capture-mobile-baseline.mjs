#!/usr/bin/env node
/**
 * Mobile Visual Baseline — Phase 1.0 of MOBILE_PLAN.md
 *
 * Снимает скриншоты 8 ключевых страниц на 3 viewport-ах (phone/tablet/desktop)
 * и сохраняет в frontend/e2e/baseline/<viewport>/<page>.png
 *
 * Использование:
 *   node scripts/capture-mobile-baseline.mjs
 *
 * Требования:
 *   - Vite dev-сервер запущен на http://127.0.0.1:1420 (или :5173)
 *   - Backend (FastAPI) на :55245
 *   - playwright установлен (npm i -D playwright && npx playwright install chromium)
 *
 * Выход: 24 PNG-файла, по 8 на viewport.
 *
 * ВАЖНО: это "as-is" снимок ТЕКУЩЕГО (pre-mobile-fix) состояния приложения.
 * После Phase 1.5+ скриншоты могут расходиться с этим baseline — это
 * ожидаемо и проверяется через Playwright visual diff в Phase 4+.
 */

import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
// Resolve baseline dir from CWD so the script works whether it's invoked
// from the repo root (`node scripts/capture-mobile-baseline.mjs`) or
// from frontend/ (`node scripts/capture-mobile-baseline.mjs`).
// Walks up to find `frontend/e2e/baseline` so CWD-relative resolution
// doesn't double-up.
function resolveBaselineDir() {
  let dir = process.cwd();
  for (let i = 0; i < 5; i++) {
    const candidate = resolve(dir, 'frontend/e2e/baseline');
    if (existsSync(candidate)) return candidate;
    const parent = resolve(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  // Fallback: relative to script location (frontend/scripts/ → frontend/)
  return resolve(__dirname, '..', 'e2e/baseline');
}
const BASELINE_DIR = process.env.OUT_DIR ?? resolveBaselineDir();

const BASE_URL = process.env.BASELINE_URL ?? 'http://127.0.0.1:1420';

/** Viewport presets — соответствуют MOBILE_PLAN.md §Целевые viewport-ы. */
const VIEWPORTS = {
  '390': { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  '768': { width: 768, height: 1024, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  '1280': { width: 1280, height: 800, deviceScaleFactor: 1, isMobile: false, hasTouch: false },
};

/**
 * 8 страниц для baseline. Hash-роутинг SPA — поэтому URL вида
 * `http://127.0.0.1:1420/#/path`. НЕ ждём сетевых idle на SSE-стримах
 * (страница Chat может висеть с открытым EventSource).
 */
const PAGES = [
  { name: '01-dashboard',     hash: '/',                      wait: 800 },
  { name: '02-bots',          hash: '/bots',                  wait: 800 },
  { name: '03-personas',      hash: '/personas',              wait: 800 },
  { name: '04-settings',      hash: '/settings',              wait: 800 },
  { name: '05-bot-preview',   hash: '/bot/2',                 wait: 1200 }, // hero-image
  { name: '06-chat',          hash: '/chat?bot=2&thread=1',   wait: 1500 }, // messages load
  { name: '07-bot-create',    hash: '/bots/create',           wait: 800 },
  { name: '08-ui-kit',        hash: '/ui-kit',                wait: 1000 },
];

async function main() {
  console.log(`📸 Mobile baseline capture`);
  console.log(`   URL:   ${BASE_URL}`);
  console.log(`   Out:   ${BASELINE_DIR}`);
  console.log(`   Total: ${Object.keys(VIEWPORTS).length} viewports × ${PAGES.length} pages = ${Object.keys(VIEWPORTS).length * PAGES.length} PNGs\n`);

  const browser = await chromium.launch({ headless: true });
  let totalCaptured = 0;
  let totalErrors = 0;

  for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
    console.log(`\n📐 Viewport ${vpName} (${vp.width}×${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: vp.deviceScaleFactor,
      isMobile: vp.isMobile,
      hasTouch: vp.hasTouch,
      // Raycast-стиль — dark theme по умолчанию (matches DESIGN.md §Colors)
      colorScheme: 'dark',
    });
    const page = await context.newPage();

    // Pre-warm: open root once to establish session/cookies, then navigate by hash
    try {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 10_000 });
      // Wait for the app shell (sidebar / main) to mount
      await page.waitForSelector('main', { timeout: 5_000 }).catch(() => {});
    } catch (e) {
      console.error(`   ❌ Cannot reach ${BASE_URL}: ${e.message}`);
      totalErrors++;
      await context.close();
      continue;
    }

    for (const p of PAGES) {
      const url = `${BASE_URL}/#${p.hash}`;
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 10_000 });
        // Disable animations for stable snapshots
        await page.addStyleTag({
          content: `*, *::before, *::after {
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
          }`,
        });
        await page.waitForTimeout(p.wait);

        const outPath = resolve(BASELINE_DIR, vpName, `${p.name}.png`);
        await mkdir(dirname(outPath), { recursive: true });
        // fullPage=true чтобы захватить scrollable контент (cards grid, settings tabs)
        await page.screenshot({ path: outPath, fullPage: true });
        console.log(`   ✓ ${p.name}.png`);
        totalCaptured++;
      } catch (e) {
        console.error(`   ✗ ${p.name}: ${e.message}`);
        totalErrors++;
      }
    }

    await context.close();
  }

  await browser.close();

  console.log(`\n${'='.repeat(50)}`);
  console.log(`✅ Captured: ${totalCaptured}`);
  console.log(`❌ Errors:   ${totalErrors}`);
  console.log(`${'='.repeat(50)}`);
  process.exit(totalErrors > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error('FATAL:', e);
  process.exit(1);
});