import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import MarkdownRenderer from '../MarkdownRenderer.svelte';

describe('MarkdownRenderer', () => {
  it('wraps fenced code blocks with copy-button wrapper + data-lang', () => {
    const { container } = render(MarkdownRenderer, {
      content: '```python\nprint(1)\n```',
    });
    const wrapper = container.querySelector('.code-block-wrapper');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('data-lang')).toBe('python');
    const btn = wrapper?.querySelector('.code-copy-btn');
    expect(btn).toBeTruthy();
    // Highlight.js adds span markup inside the code element.
    const code = wrapper?.querySelector('code');
    expect(code?.classList.contains('hljs')).toBe(true);
    expect(code?.classList.contains('language-python')).toBe(true);
  });

  it('shows a visible language label in the code block header', () => {
    const { container } = render(MarkdownRenderer, {
      content: '```typescript\nconst x = 1;\n```',
    });
    const label = container.querySelector('.code-lang-label');
    expect(label).toBeTruthy();
    expect(label?.textContent).toBe('TYPESCRIPT');
    const header = container.querySelector('.code-block-header');
    expect(header).toBeTruthy();
  });

  it('falls back to PLAINTEXT for unknown languages', () => {
    const { container } = render(MarkdownRenderer, {
      content: '```notareallanguage\nfoo bar\n```',
    });
    const wrapper = container.querySelector('.code-block-wrapper');
    expect(wrapper?.getAttribute('data-lang')).toBe('plaintext');
    expect(container.querySelector('.code-lang-label')?.textContent).toBe('PLAINTEXT');
  });

  it('renders markdown tables with header + body rows', () => {
    const { container } = render(MarkdownRenderer, {
      content: '| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |',
    });
    expect(container.querySelector('table')).toBeTruthy();
    expect(container.querySelectorAll('thead th')).toHaveLength(2);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
  });

  it('renders unordered lists with bullets', () => {
    const { container } = render(MarkdownRenderer, {
      content: '- one\n- two\n- three',
    });
    const items = container.querySelectorAll('ul li');
    expect(items).toHaveLength(3);
    expect(items[0]?.textContent?.trim()).toBe('one');
    // Tailwind preflight resets markers — our scoped CSS restores
    // them. Lock in that the restoration is in place so a future
    // preflight upgrade can't silently kill list markers again.
    const ul = container.querySelector('ul');
    expect(ul).toBeTruthy();
    const ulStyle = getComputedStyle(ul!);
    expect(ulStyle.listStyleType).toBe('disc');
  });

  it('renders ordered lists with numbers', () => {
    const { container } = render(MarkdownRenderer, {
      content: '1. first\n2. second\n3. third',
    });
    const items = container.querySelectorAll('ol li');
    expect(items).toHaveLength(3);
    const ol = container.querySelector('ol');
    expect(getComputedStyle(ol!).listStyleType).toBe('decimal');
  });

  it('returns empty container when content is empty', () => {
    const { container } = render(MarkdownRenderer, { content: '' });
    // No streaming → no render at all.
    expect(container.querySelector('.markdown')).toBeNull();
  });

  it('shows a typing cursor placeholder when streaming with no content', () => {
    const { container } = render(MarkdownRenderer, {
      content: '',
      isLast: true,
      streaming: true,
    });
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('renders inline code without the wrapper class', () => {
    const { container } = render(MarkdownRenderer, {
      content: 'Use `npm install` to install.',
    });
    const inlineCode = container.querySelector('p code');
    expect(inlineCode).toBeTruthy();
    // Inline code lives inside <p>, not inside .code-block-wrapper.
    expect(inlineCode?.closest('.code-block-wrapper')).toBeNull();
  });

  it('renders horizontal rule as <hr>', () => {
    const { container } = render(MarkdownRenderer, {
      content: 'above\n\n---\n\nbelow',
    });
    expect(container.querySelector('hr')).toBeTruthy();
  });
});
