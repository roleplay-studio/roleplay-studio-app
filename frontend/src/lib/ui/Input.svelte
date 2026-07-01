<script lang="ts">
  let {
    class: className = '',
    disabled = false,
    error = '',
    label = '',
    oninput,
    placeholder = '',
    rows = 3,
    textarea = false,
    type = 'text',
    value = $bindable(''),
  }: {
    class?: string;
    disabled?: boolean;
    error?: string;
    label?: string;
    oninput?: (e: Event) => void;
    placeholder?: string;
    rows?: number;
    textarea?: boolean;
    type?: string;
    value?: string;
  } = $props();
</script>

<div class="ri-wrap {className}">
  {#if label}
    <label class="ri-label">{label}</label>
  {/if}

  {#if textarea}
    <textarea
      bind:value
      {placeholder}
      {disabled}
      {rows}
      {oninput}
      class="ri-field ri-ta {error ? 'ri-error' : ''}"
    ></textarea>
  {:else}
    <input
      {type}
      bind:value
      {placeholder}
      {disabled}
      {oninput}
      class="ri-field {error ? 'ri-error' : ''}"
    />
  {/if}

  {#if error}
    <p class="ri-err">{error}</p>
  {/if}
</div>

<style>
  .ri-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .ri-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary, #9c9c9d);
    letter-spacing: 0.2px;
  }
  .ri-field {
    background: var(--ray-bg, #07080a);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--ray-text, #f9f9f9);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    padding: 10px 14px;
    letter-spacing: 0.2px;
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  .ri-field:focus {
    border-color: var(--ray-blue, hsl(202, 100%, 67%));
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent);
  }
  .ri-field::placeholder {
    color: var(--ray-text-tertiary, #6a6b6c);
  }
  .ri-field:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .ri-field.ri-error {
    border-color: var(--ray-red, #ff6363);
  }
  .ri-ta {
    resize: vertical;
    min-height: 60px;
    line-height: 1.5;
    field-sizing: content;
  }
  .ri-err {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-red, #ff6363);
    letter-spacing: 0.2px;
    margin: 0;
  }
</style>
