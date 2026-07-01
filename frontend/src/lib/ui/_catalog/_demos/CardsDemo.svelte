<!-- CardsDemo.svelte — Card component, all variants (bordered/hover/header/footer) -->
<script lang="ts">
  import Card from '../../Card.svelte';
</script>

<div class="cd-stack">
  <Card>
    <p>Basic card — just body content with default padding and border.</p>
  </Card>
  <Card hover>
    <p>Hoverable card — try hovering me to see the lift effect.</p>
  </Card>
  <Card padding={false}>
    {#snippet header()}
      Card with header &amp; footer
    {/snippet}
    <p>
      This card has a header and footer separated by subtle dividers. Useful for forms, dialogs, and
      grouped content.
    </p>
    {#snippet footer()}
      <small>Last updated: today</small>
    {/snippet}
  </Card>
  <Card bordered={false}>
    <p>
      Borderless card — same shadow, no border. Useful inside other containers where the border is
      redundant.
    </p>
  </Card>
</div>

<style>
  .cd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  p {
    margin: 0;
    font-family: 'Maple Mono', monospace;
    font-size: 13px;
    color: var(--ray-text-secondary);
    line-height: 1.5;
  }
  small {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
  }
</style>
