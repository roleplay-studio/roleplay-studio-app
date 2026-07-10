/**
 * DashboardPage — root page of the app once setup is done.
 *
 * The dashboard renders a list of recent threads. We don't
 * anchor on the locale-dependent title; the ``main`` element
 * with the route hash is the only stable signal that we
 * navigated to "/" successfully.
 */
import type { Page, Locator } from '@playwright/test';
import { BasePage } from './BasePage';

export class DashboardPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  get main(): Locator {
    return this.page.locator('main');
  }

  /** Body of the main viewport — what the user actually sees. */
  get content(): Locator {
    return this.page.locator('main').first();
  }

  async waitForDashboard(): Promise<void> {
    await this.waitForAppReady();
    // Sidebar render implies App.svelte resolved the boot state
    // (no wizard, no error screen). The URL itself may or may
    // not carry the trailing "#/" depending on whether the user
    // was redirected from "/connect" — so we don't anchor on it.
    await this.page.waitForFunction(
      () => !!document.querySelector('aside.sb-root nav'),
      null,
      { timeout: 5_000 },
    );
  }
}
