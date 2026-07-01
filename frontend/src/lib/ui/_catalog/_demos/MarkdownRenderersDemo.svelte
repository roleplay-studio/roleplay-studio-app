<!-- MarkdownRenderersDemo.svelte — markdown rendering with XSS-safe sanitization -->
<script lang="ts">
  import MarkdownRenderer from '../../../MarkdownRenderer.svelte';

  const HEADINGS = `# Welcome

This is **bold**, this is *italic*, this is \`inline code\`.

## Subsection

- Item one
- Item two
- Item three`;

  const CODE = `Inline \`const x = 42\` example.

\`\`\`js
function greet(name) {
  return \`Hello, \${name}!\`;
}
\`\`\`

> Blockquote: this is a quoted passage from a longer text.`;
</script>

<div class="mrd-stack">
  <div class="mrd-group">
    <span class="mrd-label">Headings + emphasis</span>
    <MarkdownRenderer content={HEADINGS} />
  </div>
  <div class="mrd-group">
    <span class="mrd-label">Code block + blockquote</span>
    <MarkdownRenderer content={CODE} />
  </div>
  <div class="mrd-group">
    <span class="mrd-label">Streaming (last, empty)</span>
    <MarkdownRenderer content="" isLast={true} streaming={true} />
  </div>
</div>

<style>
  .mrd-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .mrd-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 14px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 3%, transparent);
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 8px;
  }
  .mrd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
</style>
