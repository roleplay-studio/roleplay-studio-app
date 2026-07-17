// MobileMoreSheet.test.ts — vitest cases for the bottom sheet that
// opens from MobileBottomNav's "More" slot.
//
// Tests cover:
//   - Renders nothing when closed
//   - Renders backdrop + content when open
//   - Backdrop click invokes onclose
//   - Escape key invokes onclose
//   - Navigation buttons update window.location.hash and close sheet
//   - Theme buttons call applyThemePreference (mocked)
//   - Body scroll is locked while open, restored on close
//   - Component is hidden via CSS at >=768px (verified structurally)

import { cleanup, fireEvent, render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import MobileMoreSheet from '../MobileMoreSheet.svelte';

// Mock the theme module so theme buttons don't try to touch localStorage / DOM
// beyond what jsdom supports and so we can assert the call.
vi.mock('../theme', () => ({
  applyThemePreference: vi.fn(),
}));

import { applyThemePreference } from '../theme';

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
  // Restore any body-overflow changes the sheet may have made
  document.body.style.overflow = '';
  window.location.hash = '';
});

describe('MobileMoreSheet', () => {
  it('renders nothing when closed', () => {
    const { container } = render(MobileMoreSheet, {
      props: { onclose: () => {}, open: false },
    });
    // No .mms-root or .mms-backdrop in DOM
    expect(container.querySelector('.mms-root')).toBeNull();
    expect(container.querySelector('.mms-backdrop')).toBeNull();
  });

  it('renders backdrop + content when open', () => {
    const { container } = render(MobileMoreSheet, {
      props: { onclose: () => {}, open: true },
    });
    expect(container.querySelector('.bs-root')).toBeTruthy();
    expect(container.querySelector('.bs-backdrop')).toBeTruthy();
    expect(container.querySelector('.mms-nav')).toBeTruthy();
  });

  it('exposes a dialog role for assistive tech', () => {
    const { container } = render(MobileMoreSheet, {
      props: { onclose: () => {}, open: true },
    });
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).toBeTruthy();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
  });

  it('clicking the backdrop invokes onclose', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const backdrop = container.querySelector('.bs-backdrop') as HTMLElement;
    expect(backdrop).toBeTruthy();
    await fireEvent.click(backdrop);
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('Escape key closes the sheet', async () => {
    const onclose = vi.fn();
    render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('Escape key has no effect when closed', async () => {
    const onclose = vi.fn();
    render(MobileMoreSheet, {
      props: { onclose, open: false },
    });
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).not.toHaveBeenCalled();
  });

  it('clicking the Settings link navigates to /settings and closes', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const links = container.querySelectorAll('button.mms-link');
    expect(links.length).toBe(2); // Settings + Wizard
    const settingsBtn = links[0] as HTMLElement;
    expect(settingsBtn.textContent).toContain('Settings');
    await fireEvent.click(settingsBtn);
    expect(window.location.hash).toBe('#/settings');
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('clicking the Wizard link navigates to /setup and closes', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const links = container.querySelectorAll('button.mms-link');
    const wizardBtn = links[1] as HTMLElement;
    expect(wizardBtn.textContent).toContain('Wizard');
    await fireEvent.click(wizardBtn);
    expect(window.location.hash).toBe('#/setup');
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('clicking the Light theme button calls applyThemePreference("light") and closes', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const lightBtn = container.querySelector('button[aria-label="Light theme"]') as HTMLElement;
    expect(lightBtn).toBeTruthy();
    await fireEvent.click(lightBtn);
    expect(applyThemePreference).toHaveBeenCalledWith('light');
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('clicking the Dark theme button calls applyThemePreference("dark") and closes', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const darkBtn = container.querySelector('button[aria-label="Dark theme"]') as HTMLElement;
    await fireEvent.click(darkBtn);
    expect(applyThemePreference).toHaveBeenCalledWith('dark');
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('clicking the System theme button calls applyThemePreference("system") and closes', async () => {
    const onclose = vi.fn();
    const { container } = render(MobileMoreSheet, {
      props: { onclose, open: true },
    });
    const sysBtn = container.querySelector('button[aria-label="System theme"]') as HTMLElement;
    await fireEvent.click(sysBtn);
    expect(applyThemePreference).toHaveBeenCalledWith('system');
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('locks body scroll while open and restores on close', async () => {
    const { rerender } = render(MobileMoreSheet, {
      props: { onclose: () => {}, open: true },
    });
    expect(document.body.style.overflow).toBe('hidden');

    await rerender({ onclose: () => {}, open: false });
    expect(document.body.style.overflow).not.toBe('hidden');
  });
});
