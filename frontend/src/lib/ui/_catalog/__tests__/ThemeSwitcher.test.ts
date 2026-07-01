// __tests__/ThemeSwitcher.test.ts
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import ThemeSwitcher from '../_components/ThemeSwitcher.svelte';

afterEach(() => cleanup());

describe('ThemeSwitcher', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
  });
  afterEach(() => {
    document.documentElement.classList.remove('dark');
  });

  it('toggles .dark class on <html> when Dark is clicked', async () => {
    render(ThemeSwitcher);
    await fireEvent.click(screen.getByRole('button', { name: /Dark/ }));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('removes .dark class when Light is clicked', async () => {
    document.documentElement.classList.add('dark');
    render(ThemeSwitcher);
    await fireEvent.click(screen.getByRole('button', { name: /Light/ }));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('renders both buttons in the toggle group', () => {
    const { container } = render(ThemeSwitcher);
    const group = container.querySelector('[role="group"]');
    expect(group).toBeTruthy();
    const buttons = group?.querySelectorAll('button');
    expect(buttons).toHaveLength(2);
  });

  it('marks the active theme button with .ts-active', async () => {
    render(ThemeSwitcher);
    const lightBtn = screen.getByRole('button', { name: /Light/ });
    const darkBtn = screen.getByRole('button', { name: /Dark/ });
    // Initial: light is active
    expect(lightBtn.className).toContain('ts-active');
    expect(darkBtn.className).not.toContain('ts-active');
    // Switch to dark
    await fireEvent.click(darkBtn);
    expect(lightBtn.className).not.toContain('ts-active');
    expect(darkBtn.className).toContain('ts-active');
  });
});
