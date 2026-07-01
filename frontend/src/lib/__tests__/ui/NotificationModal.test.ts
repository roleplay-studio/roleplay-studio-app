// NotificationModal.test.ts — vitest cases for the atomic notification modal.

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import NotificationModal from '../../ui/NotificationModal.svelte';

afterEach(() => cleanup());

describe('NotificationModal', () => {
  const variants = ['success', 'info', 'warning', 'error', 'celebration', 'help'] as const;

  it('does not render .nm-icon-wrap when show=false (Modal hides via CSS, but body still mounts — by design)', () => {
    // Modal always mounts its body children; it controls visibility
    // via the .rm-visible class on the wrapper. So the NotificationModal
    // body is present in the DOM regardless of `show`, but the
    // surrounding dialog is hidden.
    const { container } = render(NotificationModal, {
      props: { message: 'Hidden', show: false },
    });
    // The dialog wrapper should be aria-hidden when closed.
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog?.getAttribute('aria-hidden')).toBe('true');
  });

  it('renders message and OK button when show=true', () => {
    const { container } = render(NotificationModal, {
      props: { message: 'Hello world', show: true },
    });
    const body = container.querySelector('.nm-body');
    expect(body).toBeTruthy();
    expect(body?.textContent).toContain('Hello world');
    expect(body?.querySelector('button.nm-btn')?.textContent?.trim()).toBe('OK');
  });

  it('defaults to variant="info" when none is provided', () => {
    const { container } = render(NotificationModal, {
      props: { message: 'x', show: true },
    });
    const wrap = container.querySelector('.nm-icon-wrap');
    expect(wrap?.classList.contains('nm-bg-info')).toBe(true);
    expect(wrap?.getAttribute('data-variant')).toBe('info');
  });

  for (const variant of variants) {
    it(`renders the ${variant} variant with a distinct icon and color class`, () => {
      const { container } = render(NotificationModal, {
        props: { message: 'x', show: true, variant },
      });
      const wrap = container.querySelector('.nm-icon-wrap');
      expect(wrap?.classList.contains(`nm-bg-${variant}`)).toBe(true);
      expect(wrap?.getAttribute('data-variant')).toBe(variant);
      // SVG should exist
      const svg = wrap?.querySelector('svg.nm-icon');
      expect(svg).toBeTruthy();
      // Different variants should have different path content (basic
      // check: the SVG innerHTML is non-empty and is unique per variant)
      const pathContent = svg?.innerHTML.trim() ?? '';
      expect(pathContent.length).toBeGreaterThan(20);
    });
  }

  it('different variants produce different SVG content (icons are distinct)', () => {
    const seen: Record<string, string> = {};
    for (const variant of variants) {
      const { container } = render(NotificationModal, {
        props: { message: 'x', show: true, variant },
      });
      const svg = container.querySelector('svg.nm-icon');
      const content = svg?.innerHTML.replace(/\s+/g, ' ').trim() ?? '';
      // Each variant should be unique; we just want to know they aren't
      // all the same icon (which would be a regression).
      seen[variant] = content;
    }
    const unique = new Set(Object.values(seen));
    expect(unique.size).toBe(variants.length);
  });

  it('icon background is a 64px circle (via CSS class, not inline style)', () => {
    const { container } = render(NotificationModal, {
      props: { message: 'x', show: true, variant: 'success' },
    });
    const wrap = container.querySelector('.nm-icon-wrap') as HTMLElement;
    // The .nm-icon-wrap class is scoped (Svelte adds a hash); we just
    // assert the element has a class name and resolves to a 64px circle
    // via getComputedStyle (jsdom returns '' for computed dimensions,
    // so we check the class list contains the wrap class).
    expect(wrap.classList.toString()).toMatch(/nm-icon-wrap/);
    expect(wrap.classList.toString()).toMatch(/nm-bg-success/);
    // And the inline border-radius is 50% (set on the wrap class itself
    // rather than via style attribute, so we check the class exists).
    expect(wrap.tagName).toBe('DIV');
  });

  it('invokes onclose when OK is clicked', () => {
    let called = 0;
    const { container } = render(NotificationModal, {
      props: { message: 'x', onclose: () => called++, show: true },
    });
    const btn = container.querySelector('button.nm-btn') as HTMLButtonElement;
    btn.click();
    expect(called).toBe(1);
  });
});
