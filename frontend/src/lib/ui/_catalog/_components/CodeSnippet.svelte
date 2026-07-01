<!-- CodeSnippet.svelte — minimal regex-based code highlighter, no deps -->
<script lang="ts">
  let {
    code = '',
    lang = 'svelte',
    title,
  }: {
    code?: string;
    lang?: 'bash' | 'svelte' | 'ts';
    title?: string;
  } = $props();

  // Set of JS/TS keywords worth highlighting. Conservative: we err on
  // the side of fewer false positives over more colors.
  const KW = new Set([
    'as',
    'async',
    'await',
    'class',
    'const',
    'default',
    'else',
    'enum',
    'export',
    'extends',
    'false',
    'for',
    'from',
    'function',
    'if',
    'import',
    'in',
    'instanceof',
    'interface',
    'let',
    'new',
    'null',
    'of',
    'return',
    'this',
    'true',
    'type',
    'typeof',
    'undefined',
    'var',
    'void',
    'while',
  ]);

  function highlight(src: string): string {
    const tokens: { cls: string; txt: string }[] = [];
    let i = 0;
    while (i < src.length) {
      const c = src[i];
      // Line comment (//...) — also matches URLs containing //, but those
      // are rare in catalog snippets; we accept the false positive.
      if (c === '/' && src[i + 1] === '/') {
        const end = src.indexOf('\n', i);
        const len = end === -1 ? src.length - i : end - i;
        tokens.push({ cls: 'cm', txt: src.slice(i, i + len) });
        i += len;
        continue;
      }
      // String literal: "..." | '...' | `...`
      if (c === '"' || c === "'" || c === '`') {
        const quote = c;
        let j = i + 1;
        while (j < src.length && src[j] !== quote) {
          if (src[j] === '\\') j++;
          j++;
        }
        j = Math.min(j + 1, src.length);
        tokens.push({ cls: 'str', txt: src.slice(i, j) });
        i = j;
        continue;
      }
      // Number literal
      if (/[0-9]/.test(c ?? '')) {
        let j = i;
        while (j < src.length && /[0-9.]/.test(src[j] ?? '')) j++;
        tokens.push({ cls: 'num', txt: src.slice(i, j) });
        i = j;
        continue;
      }
      // Identifier or keyword
      if (c && /[A-Za-z_$]/.test(c)) {
        let j = i;
        while (j < src.length && /[A-Za-z0-9_$]/.test(src[j] ?? '')) j++;
        const word = src.slice(i, j);
        tokens.push({ cls: KW.has(word) ? 'kw' : '', txt: word });
        i = j;
        continue;
      }
      // Default: pass through
      tokens.push({ cls: '', txt: c });
      i++;
    }
    return tokens
      .map((t) => {
        const esc = t.txt.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return t.cls ? `<span class="cs-${t.cls}">${esc}</span>` : esc;
      })
      .join('');
  }

  const html = $derived(highlight(code));
</script>

<div class="cs-wrap">
  {#if title}
    <div class="cs-header">
      <span class="cs-title">{title}</span>
      <span class="cs-lang">{lang}</span>
    </div>
  {/if}
  <pre class="cs-pre"><code class="cs-code">{@html html}</code></pre>
</div>

<style>
  .cs-wrap {
    border: 1px solid var(--ray-border-subtle);
    border-radius: 8px;
    overflow: hidden;
    background: var(--ray-surface-raised);
  }
  .cs-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: color-mix(in srgb, var(--ray-text) 3%, transparent);
    border-bottom: 1px solid var(--ray-border-subtle);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-secondary);
  }
  .cs-title {
    font-weight: 500;
  }
  .cs-lang {
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 9px;
    color: var(--ray-text-tertiary);
  }
  .cs-pre {
    margin: 0;
    padding: 12px 16px;
    overflow-x: auto;
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 12px;
    line-height: 1.6;
    color: var(--ray-text);
  }
  .cs-code {
    font-family: inherit;
  }
  :global(.cs-kw) {
    color: var(--ray-accent);
    font-weight: 500;
  }
  :global(.cs-str) {
    color: var(--ray-green);
  }
  :global(.cs-num) {
    color: var(--ray-yellow);
  }
  :global(.cs-cm) {
    color: var(--ray-text-tertiary);
    font-style: italic;
  }
</style>
