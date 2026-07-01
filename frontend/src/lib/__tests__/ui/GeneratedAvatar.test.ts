// GeneratedAvatar.test.ts — vitest cases for the atomic avatar component.

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import GeneratedAvatar from '../../ui/GeneratedAvatar.svelte';

afterEach(() => cleanup());

describe('GeneratedAvatar', () => {
  it('renders a div with the role="img" and an aria-label', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Luna' },
    });
    const root = container.querySelector('[role="img"]');
    expect(root).toBeTruthy();
    expect(root?.getAttribute('aria-label')).toBe('Avatar for Luna');
  });

  it('uses the custom alt prop when provided', () => {
    const { container } = render(GeneratedAvatar, {
      props: { alt: 'Bot avatar', name: 'Luna' },
    });
    expect(container.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe('Bot avatar');
  });

  it('falls back to "Avatar for ?" when name is empty', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: '' },
    });
    expect(container.querySelector('[role="img"]')?.getAttribute('aria-label')).toBe(
      'Avatar for ?',
    );
  });

  it('applies the requested size as width and height', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', size: 64 },
    });
    const root = container.querySelector('[role="img"]') as HTMLElement;
    expect(root.style.width).toBe('64px');
    expect(root.style.height).toBe('64px');
  });

  it('uses a linear-gradient background (hashed from name)', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria' },
    });
    const root = container.querySelector('[role="img"]') as HTMLElement;
    // Browsers may serialize hsl() to rgb() in inline style.background,
    // so accept either form. The key check is "linear-gradient" + 2 color stops.
    expect(root.style.background).toMatch(/^linear-gradient\(/);
    const colorMatches = root.style.background.match(/(?:hsl|rgb)\(/g) ?? [];
    expect(colorMatches.length).toBe(2);
  });

  it('same name produces same background (deterministic)', () => {
    const a = render(GeneratedAvatar, { props: { name: 'Aria' } });
    const b = render(GeneratedAvatar, { props: { name: 'Aria' } });
    const bgA = (a.container.querySelector('[role="img"]') as HTMLElement).style.background;
    const bgB = (b.container.querySelector('[role="img"]') as HTMLElement).style.background;
    // Both are linear-gradient strings with 2 stops — they should match exactly.
    expect(bgA).toBe(bgB);
    expect(bgA).toMatch(/^linear-gradient\(/);
  });

  it('circle shape uses 50% border-radius', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', shape: 'circle' },
    });
    const root = container.querySelector('[role="img"]') as HTMLElement;
    expect(root.style.borderRadius).toBe('50%');
  });

  it('rounded shape uses 22% border-radius', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', shape: 'rounded' },
    });
    expect((container.querySelector('[role="img"]') as HTMLElement).style.borderRadius).toBe('22%');
  });

  it('square shape uses 6px border-radius', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', shape: 'square' },
    });
    expect((container.querySelector('[role="img"]') as HTMLElement).style.borderRadius).toBe('6px');
  });

  it('renders an SVG face (with stroke="currentColor")', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', size: 40 },
    });
    const svg = container.querySelector('svg.ga-face');
    expect(svg).toBeTruthy();
    expect(svg?.querySelector('g[stroke="currentColor"]')).toBeTruthy();
  });

  it('face SVG is sized to ~55% of the avatar size', () => {
    const { container } = render(GeneratedAvatar, {
      props: { name: 'Aria', size: 80 },
    });
    const svg = container.querySelector('svg.ga-face');
    expect(svg?.getAttribute('width')).toBe('48');
    expect(svg?.getAttribute('height')).toBe('48');
  });
});
