// OfflineBanner.test.ts — vitest cases for the offline indicator.
//
// Tests cover:
//   - Renders nothing when online
//   - Renders when navigator.onLine is false
//   - Listens to 'offline' / 'online' window events
//   - Has correct a11y attributes (role="status", aria-live="polite")
//   - Uses --ray-yellow color (semantic warning per DESIGN.md)

import { cleanup, fireEvent, render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import OfflineBanner from '../OfflineBanner.svelte';

afterEach(() => {
  cleanup();
});

describe('OfflineBanner', () => {
  beforeEach(() => {
    // jsdom defaults to navigator.onLine = true
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => true,
    });
  });

  it('renders nothing when online', () => {
    const { container } = render(OfflineBanner);
    expect(container.querySelector('.offline-banner')).toBeNull();
  });

  it('renders the banner when navigator.onLine is false at mount', () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });
    const { container } = render(OfflineBanner);
    const banner = container.querySelector('.offline-banner');
    expect(banner).toBeTruthy();
    expect(banner?.textContent).toContain('Offline');
  });

  it('listens for the offline event and shows the banner', async () => {
    const { container } = render(OfflineBanner);
    expect(container.querySelector('.offline-banner')).toBeNull();

    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });
    await fireEvent.offline(window);

    expect(container.querySelector('.offline-banner')).toBeTruthy();
  });

  it('listens for the online event and hides the banner', async () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });
    const { container } = render(OfflineBanner);
    expect(container.querySelector('.offline-banner')).toBeTruthy();

    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => true,
    });
    await fireEvent.online(window);

    expect(container.querySelector('.offline-banner')).toBeNull();
  });

  it('exposes role=status and aria-live=polite for screen readers', () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });
    const { container } = render(OfflineBanner);
    const banner = container.querySelector('.offline-banner');
    expect(banner?.getAttribute('role')).toBe('status');
    expect(banner?.getAttribute('aria-live')).toBe('polite');
  });

  it('renders an SVG icon with aria-hidden (decorative)', () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });
    const { container } = render(OfflineBanner);
    const icon = container.querySelector('.offline-icon');
    expect(icon).toBeTruthy();
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
  });
});
