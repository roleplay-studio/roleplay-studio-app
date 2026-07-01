import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Button from '../../ui/Button.svelte';

describe('Button', () => {
  it('renders as <button> by default', () => {
    const { container } = render(Button);
    const btn = container.querySelector('button');
    expect(btn).toBeTruthy();
    expect(btn?.className).toContain('rb');
  });

  it('renders as <a> when href is set', () => {
    const { container } = render(Button, {
      props: { href: '/somewhere' },
    });
    const link = container.querySelector('a');
    expect(link).toBeTruthy();
    expect(link?.getAttribute('href')).toBe('/somewhere');
  });

  it('applies variant class', () => {
    const { container } = render(Button, {
      props: { variant: 'outline' },
    });
    const btn = container.querySelector('button');
    expect(btn?.className).toContain('rb-outline');
  });

  it('applies size class when not md', () => {
    const { container } = render(Button, {
      props: { size: 'sm' },
    });
    const btn = container.querySelector('button');
    expect(btn?.className).toContain('rb-sm');
  });

  it('applies size class for md (default)', () => {
    // Bug fix: previously `rb-md` was omitted on the assumption that "md" was
    // implicit, but the `.rb-md` rule is the only one that defines padding for
    // the default size. The size class is now always emitted.
    const { container } = render(Button);
    const btn = container.querySelector('button');
    expect(btn?.className).toContain('rb-md');
  });

  it('fires onclick when clicked', async () => {
    const clicks: MouseEvent[] = [];
    const { container } = render(Button, {
      props: {
        onclick: (e: MouseEvent) => clicks.push(e),
      },
    });
    const btn = container.querySelector('button')!;
    await fireEvent.click(btn);
    expect(clicks).toHaveLength(1);
  });

  it('is disabled when disabled prop is set', () => {
    const { container } = render(Button, {
      props: { disabled: true },
    });
    const btn = container.querySelector('button');
    expect(btn?.disabled).toBe(true);
    expect(btn?.className).toContain('rb-disabled');
  });

  it('shows loading spinner when loading', () => {
    const { container } = render(Button, {
      props: { loading: true },
    });
    // The component renders a spinner when loading=true; check for any
    // spinner-like element. The exact class is implementation-detail.
    const spinner = container.querySelector(
      '[aria-busy="true"], .rb-spinner, [class*="loading"], [class*="spinner"]',
    );
    expect(spinner).toBeTruthy();
  });
});
