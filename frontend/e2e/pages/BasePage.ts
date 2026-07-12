/**
 * BasePage — root helpers shared across all page objects.
 *
 * Hash routing — every navigation goes through
 * ``window.location.hash``. Playwright's ``page.goto`` would force
 * a full reload, so we use ``page.evaluate`` to mutate the hash
 * and trigger Svelte's ``hashchange`` listener. The exception is
 * the very first visit: ``page.goto('/')`` runs before Svelte
 * has had a chance to wire the listener, so a fresh navigation
 * is the right primitive there.
 */
import type { Page, Locator } from '@playwright/test';

export class BasePage {
  constructor(public readonly page: Page) {}

  /** Navigate to a hash route without a full reload. */
  async gotoHash(hashPath: string): Promise<void> {
    const target = hashPath.startsWith('#') ? hashPath : `#${hashPath}`;
    await this.page.evaluate((h) => {
      window.location.hash = h;
    }, target);
    // The hashchange handler dispatches synchronously; wait for
    // the next tick so route-dependent renders settle.
    await this.page.waitForTimeout(50);
  }

  /** First goto that needs a real URL load. */
  async gotoRoot(): Promise<void> {
    await this.page.goto('/');
  }

  /**
   * Healthcheck — until the splash dissolves into a real page,
   * App.svelte polls /api/health with exponential backoff. We
   * wait for the side bar root to render as evidence the app
   * booted past splash. The user-visible nav text is locale-
   * dependent (Russian vs English vs …), so we anchor on the
   * stable ``aside.sb-root`` selector rather than the label.
   */
  async waitForAppReady(): Promise<void> {
    await this.page.waitForSelector('aside.sb-root', { timeout: 30_000 });
  }

  locator(selector: string): Locator {
    return this.page.locator(selector);
  }
}
