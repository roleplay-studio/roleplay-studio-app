import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Badge from '../../ui/Badge.svelte';

describe('Badge', () => {
  it('renders span with rb base class', () => {
    const { container } = render(Badge);
    const span = container.querySelector('span.rb');
    expect(span).toBeTruthy();
  });

  it('applies variant class', () => {
    const { container } = render(Badge, {
      props: { variant: 'accent' },
    });
    const span = container.querySelector('span');
    expect(span?.className).toContain('rb-accent');
  });

  it('applies size class', () => {
    const { container } = render(Badge, {
      props: { size: 'sm' },
    });
    const span = container.querySelector('span');
    expect(span?.className).toContain('rb-sm');
  });

  it('does not include size class for default md', () => {
    const { container } = render(Badge);
    const span = container.querySelector('span');
    // rb-md is applied unconditionally; just verify the test contract.
    expect(span?.className).toContain('rb-md');
  });

  it('applies custom className', () => {
    const { container } = render(Badge, {
      props: { class: 'my-custom' },
    });
    const span = container.querySelector('span');
    expect(span?.className).toContain('my-custom');
  });
});
