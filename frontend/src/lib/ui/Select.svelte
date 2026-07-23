<script lang="ts">
  let {
    class: className = '',
    disabled = false,
    error = '',
    label = '',
    onchange,
    options = [],
    placeholder = '',
    value = $bindable(''),
  }: {
    class?: string;
    disabled?: boolean;
    error?: string;
    label?: string;
    /**
     * Fired when the user picks an option. Receives the new value
     * as the first argument and the synthetic Event as the second.
     * Backward-compatible: callbacks that only consume the Event
     * argument keep working unchanged.
     */
    onchange?: (newValue: string, e: Event) => void;
    options?: Array<{ label: string; value: string }>;
    placeholder?: string;
    value?: string;
  } = $props();

  let open = $state(false);

  function select(val: string) {
    value = val;
    open = false;
    if (onchange) {
      // Pass the new value first so callers can intercept the
      // selection BEFORE the bind:value write completes — useful for
      // confirm-modals, dirty-state checks, and the like.
      onchange(val, new Event('change'));
    }
  }
</script>

<div class="ray-select-wrap {className}">
  {#if label}
    <label class="ray-select-label">{label}</label>
  {/if}

  <div class="ray-select-container" class:disabled>
    <button
      class="ray-select-trigger"
      class:open
      class:error={!!error}
      onclick={() => {
        if (!disabled) open = !open;
      }}
      {disabled}
      type="button"
    >
      <span class="ray-select-text" class:placeholder={!value && !!placeholder}>
        {options.find((o) => o.value === value)?.label || placeholder || 'Select...'}
      </span>
      <svg
        class="ray-select-chevron"
        class:open
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    {#if open}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div class="ray-select-backdrop" onclick={() => (open = false)} role="presentation"></div>
      <div class="ray-select-panel" role="listbox">
        {#each options as opt (opt.value)}
          <button
            class="ray-select-option"
            class:selected={opt.value === value}
            role="option"
            aria-selected={opt.value === value}
            onclick={() => select(opt.value)}
            type="button"
          >
            {opt.label}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if error}
    <p class="ray-select-error">{error}</p>
  {/if}
</div>

<style>
  .ray-select-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .ray-select-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary, #9c9c9d);
    letter-spacing: 0.2px;
  }
  .ray-select-container {
    position: relative;
  }
  .ray-select-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 10px 14px;
    background: var(--ray-bg, #07080a);
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--ray-text, #f9f9f9);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: border-color 0.15s ease;
    line-height: 1.4;
  }
  .ray-select-trigger:hover:not(:disabled) {
    border-color: var(--ray-border-strong, rgba(255, 255, 255, 0.15));
  }
  .ray-select-trigger:focus-visible {
    border-color: var(--ray-blue, hsl(202, 100%, 67%));
    outline: none;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent);
  }
  .ray-select-trigger.error {
    border-color: var(--ray-red, #ff6363);
  }
  .ray-select-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ray-select-text.placeholder {
    color: var(--ray-text-tertiary, #6a6b6c);
  }
  .ray-select-chevron {
    flex-shrink: 0;
    color: var(--ray-text-secondary, #9c9c9d);
    transition: transform 0.2s ease;
    margin-left: 8px;
  }
  .ray-select-chevron.open {
    transform: rotate(180deg);
  }

  /* Backdrop for click-outside */
  .ray-select-backdrop {
    position: fixed;
    inset: 0;
    z-index: 48;
  }

  .ray-select-panel {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    background: var(--ray-overlay, #1b1c1e);
    border: 1px solid var(--ray-border, rgba(255, 255, 255, 0.06));
    border-radius: 8px;
    box-shadow:
      var(--ray-shadow-ring, rgb(27, 28, 30)) 0px 0px 0px 1px,
      var(--ray-shadow-inset, rgb(7, 8, 10)) 0px 0px 0px 1px inset;
    z-index: 49;
    overflow: hidden;
  }
  .ray-select-option {
    display: block;
    width: 100%;
    padding: 10px 14px;
    border: none;
    background: transparent;
    color: var(--ray-text-secondary, #9c9c9d);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.2px;
    text-align: left;
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .ray-select-option:hover {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
    color: var(--ray-text, #f9f9f9);
  }
  .ray-select-option.selected {
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 12%, transparent);
    color: var(--ray-blue, hsl(202, 100%, 67%));
    font-weight: 500;
  }
  .ray-select-option:not(:last-child) {
    border-bottom: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
  }

  :global(.dark) .ray-select-chevron {
    color: var(--ray-text-secondary, #9c9c9d);
  }
  :global(.dark) .ray-select-text.placeholder {
    color: var(--ray-text-tertiary, #6a6b6c);
  }

  .ray-select-error {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-red, #ff6363);
    letter-spacing: 0.2px;
    margin: 0;
  }
</style>
