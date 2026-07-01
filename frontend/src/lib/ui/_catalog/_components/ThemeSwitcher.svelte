<!-- ThemeSwitcher.svelte — light/dark toggle, local-only (no localStorage) -->
<script lang="ts">
  type Theme = 'dark' | 'light';
  let theme = $state<Theme>(
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light',
  );

  $effect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  });
</script>

<div class="ts-toggle" role="group" aria-label="Theme switcher">
  <button
    class="ts-btn"
    class:ts-active={theme === 'light'}
    onclick={() => (theme = 'light')}
    type="button"
  >
    ☀ Light
  </button>
  <button
    class="ts-btn"
    class:ts-active={theme === 'dark'}
    onclick={() => (theme = 'dark')}
    type="button"
  >
    🌙 Dark
  </button>
</div>

<style>
  .ts-toggle {
    display: inline-flex;
    gap: 4px;
    padding: 3px;
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    border-radius: 10px;
    border: 1px solid var(--ray-border-subtle);
  }
  .ts-btn {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ray-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .ts-btn:hover {
    color: var(--ray-text);
  }
  .ts-btn.ts-active {
    color: var(--ray-text);
    background: var(--ray-surface);
    box-shadow:
      var(--ray-shadow-ring) 0px 0px 0px 1px,
      0 1px 3px rgba(0, 0, 0, 0.15);
  }
</style>
