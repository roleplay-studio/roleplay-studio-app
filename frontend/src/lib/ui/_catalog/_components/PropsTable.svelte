<!-- PropsTable.svelte — render a table of catalog props -->
<script lang="ts">
  import type { CatalogProp } from '../_data/catalog';
  let { props }: { props: CatalogProp[] } = $props();
</script>

<table class="pt-table">
  <thead>
    <tr>
      <th>Prop</th>
      <th>Type</th>
      <th>Default</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    {#each props as p (p.name)}
      <tr>
        <td>
          <code>{p.name}</code>
          {#if p.required}<span class="pt-req" title="required">*</span>{/if}
        </td>
        <td><code class="pt-type">{p.type}</code></td>
        <td><code>{p.default ?? '—'}</code></td>
        <td>{p.description}</td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .pt-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text);
  }
  .pt-table th,
  .pt-table td {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--ray-border-subtle);
    vertical-align: top;
  }
  .pt-table th {
    font-weight: 600;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
    background: color-mix(in srgb, var(--ray-text) 3%, transparent);
  }
  .pt-table code {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 11px;
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
    padding: 1px 5px;
    border-radius: 4px;
    color: var(--ray-text-secondary);
  }
  .pt-type {
    color: var(--ray-accent);
  }
  .pt-req {
    color: var(--ray-red);
    font-weight: 700;
    margin-left: 2px;
  }
</style>
