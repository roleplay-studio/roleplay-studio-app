// __tests__/CodeSnippet.test.ts
import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import CodeSnippet from '../_components/CodeSnippet.svelte';

afterEach(() => cleanup());

describe('CodeSnippet', () => {
  it('renders code in a <pre><code> block', () => {
    const { container } = render(CodeSnippet, {
      props: { code: 'const x = 1;', title: 'Test' },
    });
    const pre = container.querySelector('pre');
    const code = container.querySelector('code');
    expect(pre).toBeTruthy();
    expect(code).toBeTruthy();
    expect(code?.textContent).toContain('const x = 1');
  });

  it('highlights keywords with .cs-kw class', () => {
    const { container } = render(CodeSnippet, {
      props: { code: 'const x = 1;' },
    });
    const kw = container.querySelector('.cs-kw');
    expect(kw).toBeTruthy();
    expect(kw?.textContent).toBe('const');
  });

  it('highlights strings with .cs-str class', () => {
    const { container } = render(CodeSnippet, {
      props: { code: 'const s = "hello";' },
    });
    const str = container.querySelector('.cs-str');
    expect(str?.textContent).toBe('"hello"');
  });

  it('highlights line comments with .cs-cm class', () => {
    const { container } = render(CodeSnippet, {
      props: { code: '// this is a comment\nconst x = 1;' },
    });
    const cm = container.querySelector('.cs-cm');
    expect(cm?.textContent).toBe('// this is a comment');
  });

  it('renders lang badge in header when title is set', () => {
    const { container } = render(CodeSnippet, {
      props: { code: '', lang: 'ts', title: 'Example' },
    });
    const lang = container.querySelector('.cs-lang');
    expect(lang?.textContent).toBe('ts');
  });

  it('escapes HTML in user-provided code (no script injection)', () => {
    const { container } = render(CodeSnippet, {
      props: { code: 'const x = "<script>alert(1)</script>";' },
    });
    // The literal <script> tag must not appear as an element
    expect(container.querySelector('script')).toBeNull();
    // It should be present as escaped text
    const code = container.querySelector('code');
    expect(code?.textContent).toContain('"<script>');
  });
});
