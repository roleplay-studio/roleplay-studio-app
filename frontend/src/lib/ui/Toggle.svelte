<!-- Toggle — Raycast-style toggle switch -->
<script lang="ts">
  let {
    checked = $bindable(false),
    class: className = '',
    disabled = false,
    label = '',
    onchange,
  }: {
    checked?: boolean;
    class?: string;
    disabled?: boolean;
    label?: string;
    onchange?: (e: Event) => void;
  } = $props();
</script>

<label class="rtg-wrap {className}">
  <input type="checkbox" bind:checked {disabled} {onchange} class="rtg-input" />
  <span class="rtg-track">
    <span class="rtg-thumb"></span>
  </span>
  {#if label}
    <span class="rtg-label">{label}</span>
  {/if}
</label>

<style>
  .rtg-wrap {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }
  .rtg-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }
  .rtg-track {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 12%, transparent);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    transition: all 0.2s ease;
    flex-shrink: 0;
  }
  .rtg-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--ray-text-secondary, #9c9c9d);
    transition: all 0.2s ease;
  }
  .rtg-input:checked + .rtg-track {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 30%, transparent);
    border-color: var(--ray-accent, #8b5cf6);
  }
  .rtg-input:checked + .rtg-track .rtg-thumb {
    left: 18px;
    background: var(--ray-accent, #8b5cf6);
  }
  .rtg-input:disabled + .rtg-track {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .rtg-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary, #9c9c9d);
    letter-spacing: 0.2px;
  }
</style>
