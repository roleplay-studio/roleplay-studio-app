import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Loading from '../../ui/Loading.svelte';

describe('Loading', () => {
  it('renders with default props (spinner, md)', () => {
    const { container } = render(Loading);
    const span = container.querySelector('.loading');
    expect(span).toBeTruthy();
    expect(span?.className).toContain('loading-spinner');
    expect(span?.className).toContain('loading-md');
  });

  it('applies custom type', () => {
    const { container } = render(Loading, {
      props: { type: 'dots' },
    });
    const span = container.querySelector('.loading');
    expect(span?.className).toContain('loading-dots');
  });

  it('applies custom size', () => {
    const { container } = render(Loading, {
      props: { size: 'lg' },
    });
    const span = container.querySelector('.loading');
    expect(span?.className).toContain('loading-lg');
  });

  it('renders text when provided', () => {
    const { container } = render(Loading, {
      props: { text: 'Loading...' },
    });
    expect(container.textContent).toContain('Loading...');
  });

  it('does not render text when not provided', () => {
    const { container } = render(Loading);
    const textEl = container.querySelector('span.text-sm');
    expect(textEl).toBeFalsy();
  });
});
