# 📸 Mobile Visual Baseline

> **Phase 1.0 of [`docs/MOBILE_PLAN.md`](../../../docs/MOBILE_PLAN.md).**
> Captured before any mobile-specific changes — serves as the source-of-truth
> for Playwright visual-diff checks throughout Phases 2-5.

## What's here

```
baseline/
├── 390/   # iPhone 12 mini / SE (390×844, @2x DPR, touch)
├── 768/   # iPad mini portrait (768×1024, @2x DPR, touch)
└── 1280/  # Desktop (1280×800, @1x DPR, no touch)
```

Each viewport directory contains **8 PNG snapshots** of the app at its
current (pre-fix) state:

| # | Page | Hash route | Notes |
|---|---|---|---|
| 01 | Dashboard | `/` | hero + recent chats |
| 02 | Bots list | `/bots` | grid of bot cards |
| 03 | Personas | `/personas` | grid of persona cards |
| 04 | Settings | `/settings` | vertical sidebar tabs |
| 05 | Bot preview | `/bot/2` | hero image + description |
| 06 | Chat (with thread) | `/chat?bot=2&thread=1` | bubbles + input |
| 07 | Bot create | `/bots/create` | stepper + form |
| 08 | UI Kit catalog | `/ui-kit` | demos grid |

Total: **24 PNG files, ~11 MB**.

## How to regenerate

```bash
# Pre-requisites: vite dev server on :1420 + backend on :55245
cd frontend && node scripts/capture-mobile-baseline.mjs
```

The script:
- Walks all 3 viewports sequentially (single browser context each)
- Disables CSS animations (`animation-duration: 0s !important`)
- Uses `colorScheme: 'dark'` (matches Raycast-dark design intent)
- Captures `fullPage: true` so scrollable content is included
- Wait times per page are tuned (chat needs longer for SSE/load)

## How to diff in CI (Phase 4+)

Use Playwright's `toHaveScreenshot()` API:

```ts
await expect(page).toHaveScreenshot(`04-settings-${viewport}.png`, {
  maxDiffPixelRatio: 0.001, // 0.1% tolerance
});
```

Expected behavior during Phases 1-5:
- **1280 (desktop) snapshots must stay identical** — desktop layout is not in scope
- **768 (tablet) snapshots will change** in Phase 1.6 when sidebar collapses
- **390 (phone) snapshots will change a lot** in Phases 1-4 (bottom-nav, grids, sheets)

If 1280 diffs appear, that's a regression — investigate before committing.