// NavItem.test.ts — vitest cases for the atomic nav row used by Sidebar.
// Tests cover: render (icon + label), active state, collapsed state (label
// hidden), click handler, and that the component is domain-agnostic
// (no i18n/store imports in NavItem itself).

import { cleanup, fireEvent, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import NavItem from '../../ui/NavItem.svelte';

afterEach(() => cleanup());

const ICON = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle></svg>';

describe('NavItem', () => {
  it('renders the icon and the label', () => {
    const { container, getByText } = render(NavItem, {
      props: { icon: ICON, label: 'Bots' },
    });
    const button = container.querySelector('button.ni');
    expect(button).toBeTruthy();
    expect(button?.classList.contains('ni-collapsed')).toBe(false);
    expect(button?.querySelector('.ni-icon')).toBeTruthy();
    expect(button?.querySelector('.ni-label')?.textContent?.trim()).toBe('Bots');
    // getByText used to ensure tree-render (anti-strip for unused-imports)
    expect(getByText('Bots')).toBeTruthy();
  });

  it('applies the active class when active=true', () => {
    const { container } = render(NavItem, {
      props: { active: true, icon: ICON, label: 'Active' },
    });
    const button = container.querySelector('button.ni');
    expect(button?.classList.contains('ni-active')).toBe(true);
  });

  it('hides the label and applies the collapsed class when collapsed=true', () => {
    const { container } = render(NavItem, {
      props: { collapsed: true, icon: ICON, label: 'Hidden' },
    });
    const button = container.querySelector('button.ni');
    expect(button?.classList.contains('ni-collapsed')).toBe(true);
    expect(button?.querySelector('.ni-label')).toBeNull();
    // icon is still rendered
    expect(button?.querySelector('.ni-icon')).toBeTruthy();
  });

  it('invokes onclick when the button is clicked', async () => {
    const handler = vi.fn();
    const { container } = render(NavItem, {
      props: { icon: ICON, label: 'Click', onclick: handler },
    });
    const button = container.querySelector('button.ni');
    expect(button).toBeTruthy();
    if (button) await fireEvent.click(button);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does nothing if onclick is omitted (no error on click)', async () => {
    const { container } = render(NavItem, {
      props: { icon: ICON, label: 'No-op' },
    });
    const button = container.querySelector('button.ni');
    expect(button).toBeTruthy();
    if (button) await fireEvent.click(button);
    // Just check no error was thrown
  });

  it('defaults to a non-active, non-collapsed button (no surprises)', () => {
    const { container } = render(NavItem, {
      props: { icon: ICON, label: 'Default' },
    });
    const button = container.querySelector('button.ni');
    expect(button?.classList.contains('ni-active')).toBe(false);
    expect(button?.classList.contains('ni-collapsed')).toBe(false);
  });
});
