<script lang="ts">
  import DOMPurify from 'dompurify';
  import hljs from 'highlight.js/lib/core';
  import bash from 'highlight.js/lib/languages/bash';
  import css from 'highlight.js/lib/languages/css';
  import javascript from 'highlight.js/lib/languages/javascript';
  import json from 'highlight.js/lib/languages/json';
  import markdown from 'highlight.js/lib/languages/markdown';
  import python from 'highlight.js/lib/languages/python';
  import sql from 'highlight.js/lib/languages/sql';
  import typescript from 'highlight.js/lib/languages/typescript';
  import html from 'highlight.js/lib/languages/xml';
  import yamlLang from 'highlight.js/lib/languages/yaml';
  // hljs token colors are defined as CSS variables on
  // :root / .dark in app.css so they follow the active theme.
  // We do NOT import any hljs stylesheet — coloring is handled
  // by scoped rules below that target .hljs-keyword, .hljs-string,
  // etc. and read from --hljs-* variables.
  import { marked } from 'marked';

  // Register the languages we care about for chat output. Adding
  // more is one line each, but we keep the surface narrow so the
  // bundle stays small.
  hljs.registerLanguage('javascript', javascript);
  hljs.registerLanguage('js', javascript);
  hljs.registerLanguage('typescript', typescript);
  hljs.registerLanguage('ts', typescript);
  hljs.registerLanguage('python', python);
  hljs.registerLanguage('py', python);
  hljs.registerLanguage('bash', bash);
  hljs.registerLanguage('sh', bash);
  hljs.registerLanguage('shell', bash);
  hljs.registerLanguage('json', json);
  hljs.registerLanguage('yaml', yamlLang);
  hljs.registerLanguage('yml', yamlLang);
  hljs.registerLanguage('markdown', markdown);
  hljs.registerLanguage('md', markdown);
  hljs.registerLanguage('sql', sql);
  hljs.registerLanguage('html', html);
  hljs.registerLanguage('xml', html);
  hljs.registerLanguage('css', css);
  // Register 'plaintext' as a no-op language so hljs.stopWarning
  // doesn't fire when the LLM emits an unknown fence language.
  // The highlight() call returns the escaped source verbatim.
  hljs.registerLanguage('plaintext', () => ({
    aliases: ['text', 'txt'],
    contains: [],
  }));

  const {
    content = '',
    isLast = false,
    streaming = false,
  }: {
    content?: string;
    isLast?: boolean;
    streaming?: boolean;
  } = $props();

  function escapeHtml(s: string): string {
    return s.replace(/[&<>"']/g, (c) => {
      switch (c) {
        case '"':
          return '&quot;';
        case '&':
          return '&amp;';
        case "'":
          return '&#39;';
        case '<':
          return '&lt;';
        case '>':
          return '&gt;';
        default:
          return c;
      }
    });
  }

  // Custom code renderer — wraps fenced code blocks with a
  // copy-button container and runs highlight.js for syntax
  // colouring. We escape the source first, then let hljs emit
  // pre-coloured span markup on top. We also surface the
  // detected language as a visible label in the top-left.
  function codeRenderer({
    lang,
    text,
  }: {
    lang?: string;
    text: string;
  }): string {
    const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext';
    let highlighted: string;
    try {
      highlighted = hljs.highlight(text, {
        ignoreIllegals: true,
        language,
      }).value;
    } catch {
      highlighted = escapeHtml(text);
    }
    const safeLang = escapeHtml(language);
    const displayLang = safeLang.toUpperCase();
    return (
      `<div class="code-block-wrapper" data-lang="${safeLang}">` +
      `<div class="code-block-header">` +
      `<span class="code-lang-label">${displayLang}</span>` +
      `<button type="button" class="code-copy-btn" aria-label="Copy code">` +
      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>` +
      `</button>` +
      `</div>` +
      `<pre><code class="hljs language-${safeLang}">${highlighted}</code></pre>` +
      `</div>`
    );
  }

  const renderer = new marked.Renderer();
  renderer.code = codeRenderer;

  marked.setOptions({
    breaks: true,
    gfm: true,
    renderer,
  });

  const rendered = $derived(
    content
      ? DOMPurify.sanitize(marked.parse(content) as string, {
          ADD_ATTR: ['data-lang', 'data-copied', 'target', 'rel'],
        })
      : '',
  );

  // Delegated click handler — the wrapper div might be re-rendered
  // as content streams in, so we attach once to the container and
  // dispatch by closest('.code-copy-btn').
  let container: HTMLDivElement | undefined = $state();

  async function handleCopyClick(e: MouseEvent) {
    const target = e.target as HTMLElement | null;
    const btn = target?.closest('.code-copy-btn');
    if (!btn) return;
    const wrapper = btn.closest('.code-block-wrapper');
    const code = wrapper?.querySelector('code')?.textContent ?? '';
    try {
      await navigator.clipboard.writeText(code);
      btn.classList.add('copied');
      setTimeout(() => btn.classList.remove('copied'), 1500);
    } catch {
      // Clipboard API denied (insecure context, permission).
      // Silent fail — the button just doesn't confirm.
    }
  }

  $effect(() => {
    if (!container) return;
    container.addEventListener('click', handleCopyClick);
    return () => container?.removeEventListener('click', handleCopyClick);
  });
</script>

{#if content}
  <div class="markdown text-sm text-theme leading-relaxed" bind:this={container}>
    {@html rendered}
  </div>
{:else if streaming && isLast}
  <div class="markdown text-sm text-theme leading-relaxed">
    <span class="inline-block w-2 h-4 bg-surface-400 animate-pulse">▊</span>
  </div>
{/if}

<style>
  /* Code block tokens: dark-on-light on the light theme,
     pastel-on-dark on the dark theme. Both palettes are
     defined as CSS variables on `.markdown` (see top of
     <style>), so scoped CSS below can read them via
     var(--hljs-*) without specificity wars. */
  .markdown {
    /* Light theme code block: light surface, GitHub-Light
       token palette (dark-but-readable on light background). */
    --ray-code-bg: #f6f8fa;
    --ray-code-header: #eef1f4;
    --ray-code-text: #1f2328;
    --hljs-keyword: #cf222e;
    --hljs-string: #0a3069;
    --hljs-number: #0550ae;
    --hljs-comment: #6e7781;
    --hljs-function: #8250df;
    --hljs-variable: #953800;
    --hljs-tag: #116329;
    --hljs-type: #953800;
    --hljs-deletion: #82071e;
    --hljs-addition: #116329;
  }
  :global(.dark) .markdown {
    /* Dark theme code block: dark surface, GitHub-Dark
       token palette (pastel tokens on dark background). */
    --ray-code-bg: #161a1d;
    --ray-code-header: #0d1117;
    --ray-code-text: #e6edf3;
    --hljs-keyword: #ff7b72;
    --hljs-string: #a5d6ff;
    --hljs-number: #79c0ff;
    --hljs-comment: #8b949e;
    --hljs-function: #d2a8ff;
    --hljs-variable: #ffa657;
    --hljs-tag: #7ee787;
    --hljs-type: #ffa657;
    --hljs-deletion: #ffdcd7;
    --hljs-addition: #aff5b4;
  }
  .markdown :global(p) {
    margin: 0 0 0.35em 0;
  }
  .markdown :global(p:last-child) {
    margin-bottom: 0;
  }
  .markdown :global(strong) {
    color: var(--theme-text-secondary);
    font-weight: 600;
  }
  .markdown :global(em) {
    color: var(--theme-text-secondary);
  }
  .markdown :global(code) {
    background: rgba(139, 92, 246, 0.2);
    color: rgba(139, 92, 246, 0.7);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.85em;
    font-family: 'Fira Code', 'JetBrains Mono', monospace;
  }
  .markdown :global(pre) {
    background: var(--ray-code-bg);
    border: 1px solid var(--ray-border);
    border-radius: 10px;
    padding: 1em;
    overflow-x: auto;
    margin: 0.5em 0;
    /* The first line sits right under the header — pull it up a
       bit so it doesn't double-pad. */
    margin-top: 0;
  }
  .markdown :global(pre code) {
    background: none;
    color: var(--ray-code-text);
    padding: 0;
    font-size: 0.85em;
    line-height: 1.55;
  }

  /* highlight.js token colours — read from theme variables so
     light/dark mode flips automatically. */
  .markdown :global(.hljs-keyword),
  .markdown :global(.hljs-selector-tag),
  .markdown :global(.hljs-built_in) {
    color: var(--hljs-keyword);
    font-weight: 600;
  }
  .markdown :global(.hljs-string),
  .markdown :global(.hljs-attr),
  .markdown :global(.hljs-template-variable) {
    color: var(--hljs-string);
  }
  .markdown :global(.hljs-number),
  .markdown :global(.hljs-literal),
  .markdown :global(.hljs-symbol),
  .markdown :global(.hljs-bullet) {
    color: var(--hljs-number);
  }
  .markdown :global(.hljs-comment),
  .markdown :global(.hljs-quote) {
    color: var(--hljs-comment);
    font-style: italic;
  }
  .markdown :global(.hljs-function),
  .markdown :global(.hljs-title),
  .markdown :global(.hljs-class .hljs-title) {
    color: var(--hljs-function);
  }
  .markdown :global(.hljs-variable),
  .markdown :global(.hljs-name),
  .markdown :global(.hljs-attribute) {
    color: var(--hljs-variable);
  }
  .markdown :global(.hljs-tag),
  .markdown :global(.hljs-meta) {
    color: var(--hljs-tag);
  }
  .markdown :global(.hljs-type),
  .markdown :global(.hljs-params) {
    color: var(--hljs-type);
  }
  .markdown :global(.hljs-deletion) {
    color: var(--hljs-deletion);
    background: rgba(239, 68, 68, 0.15);
  }
  .markdown :global(.hljs-addition) {
    color: var(--hljs-addition);
    background: rgba(16, 185, 129, 0.15);
  }
  .markdown :global(a) {
    color: #67e8f9;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .markdown :global(a:hover) {
    color: #22d3ee;
  }
  .markdown :global(ul),
  .markdown :global(ol) {
    padding-left: 1.5em;
    margin: 0.4em 0;
  }
  /* Tailwind preflight resets list markers to none — restore
     them so ul/ol actually look like lists. */
  .markdown :global(ul) {
    list-style-type: disc;
  }
  .markdown :global(ol) {
    list-style-type: decimal;
  }
  .markdown :global(li) {
    margin: 0.2em 0;
  }
  .markdown :global(li::marker) {
    color: var(--theme-text-secondary, #9ca3af);
  }
  .markdown :global(li > ul),
  .markdown :global(li > ol) {
    margin: 0.15em 0;
  }
  .markdown :global(li > ul) {
    list-style-type: circle;
  }
  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3),
  .markdown :global(h4) {
    font-weight: 600;
    margin: 0.75em 0 0.4em 0;
  }
  .markdown :global(h1) {
    font-size: 1.2em;
  }
  .markdown :global(h2) {
    font-size: 1.1em;
  }
  .markdown :global(h3) {
    font-size: 1em;
  }
  .markdown :global(blockquote) {
    border-left: 3px solid rgba(139, 92, 246, 0.4);
    padding-left: 1em;
    color: #9ca3af;
    margin: 0.5em 0;
    font-style: italic;
  }
  .markdown :global(hr) {
    border: none;
    border-top: 1px solid rgba(139, 92, 246, 0.15);
    margin: 0.75em 0;
  }

  /* Code block wrapper with header (lang label + copy button). */
  .markdown :global(.code-block-wrapper) {
    position: relative;
    margin: 0.5em 0;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--ray-border);
    background: var(--ray-code-bg);
  }
  .markdown :global(.code-block-header) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px 6px 12px;
    background: var(--ray-code-header);
    border-bottom: 1px solid var(--ray-border-subtle);
  }
  .markdown :global(.code-lang-label) {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--theme-text-secondary, #9ca3af);
    font-family: 'Fira Code', 'JetBrains Mono', monospace;
  }
  .markdown :global(.code-copy-btn) {
    background: transparent;
    border: 1px solid var(--ray-border);
    color: var(--theme-text-secondary, #9ca3af);
    border-radius: 6px;
    padding: 3px 6px;
    cursor: pointer;
    opacity: 0.7;
    transition:
      opacity 0.15s ease,
      background 0.15s ease,
      color 0.15s ease;
    display: inline-flex;
    align-items: center;
  }
  .markdown :global(.code-block-wrapper:hover .code-copy-btn),
  .markdown :global(.code-copy-btn:focus-visible) {
    opacity: 1;
  }
  .markdown :global(.code-copy-btn:hover) {
    background: var(--ray-border-subtle);
    color: var(--theme-text, #e5e7eb);
  }
  .markdown :global(.code-copy-btn.copied) {
    background: rgba(16, 185, 129, 0.2);
    border-color: rgba(16, 185, 129, 0.5);
    color: rgb(16, 185, 129);
    opacity: 1;
  }
  /* The wrapper holds the header AND the <pre>; pre still has its
     own padding but no border/background so the wrapper shows
     through cleanly. */
  .markdown :global(.code-block-wrapper > pre) {
    border: none;
    border-radius: 0;
    margin: 0;
  }

  /* Tables. */
  .markdown :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 0.5em 0;
    font-size: 0.9em;
    border: 1px solid rgba(139, 92, 246, 0.15);
    border-radius: 6px;
    overflow: hidden;
  }
  .markdown :global(thead) {
    background: rgba(139, 92, 246, 0.08);
  }
  .markdown :global(th),
  .markdown :global(td) {
    padding: 6px 10px;
    text-align: left;
    border-bottom: 1px solid rgba(139, 92, 246, 0.1);
  }
  .markdown :global(th) {
    font-weight: 600;
    color: var(--theme-text-secondary, #c4b5fd);
  }
  .markdown :global(tbody tr:last-child td) {
    border-bottom: none;
  }
  .markdown :global(tbody tr:hover) {
    background: rgba(139, 92, 246, 0.04);
  }
</style>