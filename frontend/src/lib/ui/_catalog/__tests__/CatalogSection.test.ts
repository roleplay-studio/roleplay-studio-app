// __tests__/CatalogSection.test.ts
// Svelte 5 snippets are passed under `props` (children is a reserved
// Svelte option name in @testing-library/svelte v5).
import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import CatalogSection from '../_components/CatalogSection.svelte';

afterEach(() => cleanup());

describe('CatalogSection', () => {
  it('renders title as h2', () => {
    const { container } = render(CatalogSection, {
      props: { title: 'Buttons' },
    });
    const h2 = container.querySelector('h2');
    expect(h2?.textContent).toBe('Buttons');
  });

  it('renders description as <p> when provided', () => {
    const { container } = render(CatalogSection, {
      props: { description: 'Some context.', title: 'X' },
    });
    const p = container.querySelector('.cs-desc');
    expect(p?.textContent).toBe('Some context.');
  });

  it('omits <p> when description is missing', () => {
    const { container } = render(CatalogSection, {
      props: { title: 'X' },
    });
    expect(container.querySelector('.cs-desc')).toBeNull();
  });

  it('wraps content area in .cs-content div', () => {
    const { container } = render(CatalogSection, {
      props: { title: 'X' },
    });
    const content = container.querySelector('.cs-content');
    expect(content).toBeTruthy();
    const section = container.querySelector('section.cs-section');
    expect(section).toBeTruthy();
  });
});
