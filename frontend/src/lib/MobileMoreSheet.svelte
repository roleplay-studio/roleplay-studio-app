<!--
  MobileMoreSheet — bottom sheet for the MobileBottomNav's "More" slot.

  Phase 3.1 refactor (MOBILE_PLAN.md): the bespoke backdrop/handle/animation
  CSS was duplicated from BottomSheet. We now compose with BottomSheet
  via children snippet — keeps the file's domain logic (Settings/Wizard
  navigation + theme switcher) and removes ~120 lines of CSS.

  Hidden at >=768px via BottomSheet's own @media rule — desktop uses
  the Sidebar's nav for Settings/Wizard instead.
-->
<script lang="ts">
  import { applyThemePreference } from './theme';
  import { BottomSheet } from './ui';

  interface Props {
    onclose: () => void;
    open: boolean;
  }

  const { onclose, open }: Props = $props();

  function navigate(path: string) {
    window.location.hash = path === '/' ? '#/' : `#${path}`;
    onclose();
  }

  function setTheme(pref: 'dark' | 'light' | 'system') {
    applyThemePreference(pref);
    onclose();
  }
</script>

<BottomSheet {open} {onclose} ariaLabel="More options">
  <nav class="mms-nav" aria-label="Secondary navigation">
    <button type="button" class="mms-link" onclick={() => navigate('/settings')}>
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><circle cx="12" cy="12" r="3" /><path
          d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
        /></svg
      >
      <span>Settings</span>
    </button>

    <button type="button" class="mms-link" onclick={() => navigate('/setup')}>
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><path
          d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"
        /><path d="m14 7 3 3" /><path d="M5 6v4" /><path d="M19 14v4" /><path d="M10 2v2" /><path
          d="M7 8H3"
        /><path d="M21 16h-4" /><path d="M11 3H9" /></svg
      >
      <span>Wizard</span>
    </button>
  </nav>

  <div class="mms-divider" role="presentation"></div>

  <div class="mms-theme" role="radiogroup" aria-label="Theme">
    <span class="mms-section-label">Theme</span>
    <div class="mms-theme-row">
      <button
        type="button"
        class="mms-theme-btn"
        onclick={() => setTheme('light')}
        aria-label="Light theme"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><circle cx="12" cy="12" r="5" /><path
            d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"
          /></svg
        >
        Light
      </button>
      <button
        type="button"
        class="mms-theme-btn"
        onclick={() => setTheme('dark')}
        aria-label="Dark theme"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg
        >
        Dark
      </button>
      <button
        type="button"
        class="mms-theme-btn"
        onclick={() => setTheme('system')}
        aria-label="System theme"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></svg
        >
        System
      </button>
    </div>
  </div>

  <div class="mms-footer">
    <span class="mms-version">v0.1.0</span>
  </div>
</BottomSheet>

<style>
  .mms-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mms-link {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    padding: 10px 12px;
    border: none;
    background: transparent;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.2px;
    text-align: left;
    border-radius: 8px;
    cursor: pointer;
    transition:
      opacity 0.15s ease,
      background 0.15s ease;
  }

  .mms-link:hover {
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
  }

  .mms-link:focus-visible {
    outline: 2px solid var(--ray-blue);
    outline-offset: -2px;
  }

  .mms-divider {
    height: 1px;
    background: var(--ray-border-subtle);
    margin: 4px 0;
  }

  .mms-section-label {
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0 12px;
  }

  .mms-theme-row {
    display: flex;
    gap: 8px;
    padding: 0 12px;
  }

  .mms-theme-btn {
    flex: 1;
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border: 1px solid var(--ray-border);
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.25px;
    border-radius: 8px;
    cursor: pointer;
    transition:
      opacity 0.15s ease,
      background 0.15s ease;
  }

  .mms-theme-btn:hover {
    background: color-mix(in srgb, var(--ray-text) 6%, transparent);
    color: var(--ray-text);
  }

  .mms-theme-btn:focus-visible {
    outline: 2px solid var(--ray-blue);
    outline-offset: -2px;
  }

  .mms-footer {
    text-align: center;
    padding: 8px 0;
  }

  .mms-version {
    font-size: 10px;
    color: var(--ray-text-tertiary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    letter-spacing: 0.25px;
  }
</style>
