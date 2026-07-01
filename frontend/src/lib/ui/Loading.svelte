<script lang="ts">
  const {
    class: className = '',
    size = 'md',
    text = '',
    type = 'spinner',
  }: {
    class?: string;
    size?: 'lg' | 'md' | 'sm' | 'xl' | 'xs';
    text?: string;
    type?: 'dots' | 'spinner';
  } = $props();
</script>

<div class="flex flex-col items-center gap-2 {className}">
  <span class="loading loading-{type} loading-{size}" aria-label="loading"></span>
  {#if text}
    <span class="text-sm text-theme-secondary">{text}</span>
  {/if}
</div>
