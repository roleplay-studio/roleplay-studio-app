<!-- Textarea — auto-growing textarea with Raycast-style -->
<script lang="ts">
  import { autogrow } from './actions';

  let {
    class: className = '',
    disabled = false,
    error = '',
    hint = '',
    label = '',
    name = '',
    oninput,
    placeholder = '',
    required = false,
    resize = 'y',
    rows = 3,
    value = $bindable(''),
  }: {
    class?: string;
    disabled?: boolean;
    error?: string;
    hint?: string;
    label?: string;
    name?: string;
    oninput?: (e: Event) => void;
    placeholder?: string;
    required?: boolean;
    resize?: 'both' | 'none' | 'x' | 'y';
    rows?: number;
    value?: string;
  } = $props();
</script>

<div class="rt-wrap {className}">
  {#if label}
    <label class="rt-label" for={name}>
      {label}
      {#if required}<span class="rt-required">*</span>{/if}
    </label>
  {/if}

  <textarea
    use:autogrow
    bind:value
    {rows}
    {placeholder}
    {disabled}
    {required}
    {oninput}
    id={name}
    class="rt-field {resize === 'none'
      ? 'rt-noresize'
      : resize === 'x'
        ? 'rt-resizex'
        : resize === 'both'
          ? 'rt-resizeboth'
          : 'rt-resizey'} {error ? 'rt-field-error' : ''}"
  ></textarea>

  {#if error}
    <span class="rt-error">{error}</span>
  {:else if hint}
    <span class="rt-hint">{hint}</span>
  {/if}
</div>

<style>
  .rt-wrap {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .rt-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary, #9c9c9d);
    letter-spacing: 0.2px;
  }
  .rt-required {
    color: var(--ray-red, #ff6363);
    font-weight: 600;
  }
  .rt-field {
    background: var(--ray-bg, #07080a);
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--ray-text, #f9f9f9);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    padding: 10px 14px;
    letter-spacing: 0.2px;
    line-height: 1.5;
    transition:
      border-color 0.15s ease,
      box-shadow 0.15s ease;
    outline: none;
    width: 100%;
    box-sizing: border-box;
    min-height: 60px;
  }
  .rt-field:focus {
    border-color: var(--ray-blue, hsl(202, 100%, 67%));
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent);
  }
  .rt-field::placeholder {
    color: var(--ray-text-tertiary, #6a6b6c);
  }
  .rt-field:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .rt-field.rt-field-error {
    border-color: var(--ray-red, #ff6363);
  }
  .rt-error {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-red, #ff6363);
    letter-spacing: 0.2px;
  }
  .rt-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-tertiary, #6a6b6c);
    letter-spacing: 0.2px;
  }
  .rt-noresize {
    resize: none;
  }
  .rt-resizex {
    resize: horizontal;
  }
  .rt-resizey {
    resize: vertical;
  }
  .rt-resizeboth {
    resize: both;
  }
</style>
