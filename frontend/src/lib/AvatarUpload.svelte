<!-- AvatarUpload — avatar with upload button, generated placeholder, loading overlay -->
<script lang="ts">
  import { onMount } from 'svelte';

  import { currentLang, t } from './i18n';
  import { GeneratedAvatar, Loading } from './ui';

  let lang = $state('en');
  onMount(() => currentLang.subscribe((v) => (lang = v)));

  const {
    avatarPreview = '',
    inputId = 'avatar-upload',
    name = '',
    onupload,
    uploading = false,
  }: {
    avatarPreview?: string;
    inputId?: string;
    name?: string;
    onupload?: (e: Event) => void;
    uploading?: boolean;
  } = $props();
</script>

<div class="au-wrap">
  <label class="au-label" for={inputId}>
    {#if avatarPreview}
      <img src={avatarPreview} alt="avatar" class="au-img" />
    {:else}
      <GeneratedAvatar name={name || '?'} size={80} shape="rounded" />
    {/if}
    {#if uploading}
      <div class="au-overlay">
        <Loading size="sm" type="dots" />
      </div>
    {/if}
  </label>
  <label for={inputId} class="au-btn">
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline points="17 8 12 3 7 8"
      ></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg
    >
    {t('common.upload', lang)}
    <input id={inputId} type="file" accept="image/*" class="hidden" onchange={onupload} />
  </label>
</div>

<style>
  :root {
    --au-border: rgba(0, 0, 0, 0.06);
    --au-border-strong: rgba(0, 0, 0, 0.1);
    --au-text: #1d1d1f;
    --au-text-secondary: #6e6e73;
    --au-upload-bg: rgba(0, 0, 0, 0.04);
    --au-upload-border: rgba(0, 0, 0, 0.06);
    --au-card: #ffffff;
  }
  :root.dark {
    --au-border: rgba(255, 255, 255, 0.06);
    --au-border-strong: rgba(255, 255, 255, 0.1);
    --au-text: #f9f9f9;
    --au-text-secondary: #9c9c9d;
    --au-upload-bg: rgba(255, 255, 255, 0.04);
    --au-upload-border: rgba(255, 255, 255, 0.06);
    --au-card: #101111;
  }

  .au-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  .au-label {
    cursor: pointer;
    position: relative;
    display: block;
  }
  .au-img {
    width: 80px;
    height: 80px;
    border-radius: 12px;
    object-fit: cover;
    box-shadow: 0 4px 12px color-mix(in srgb, #000 20%, transparent);
    border: 1px solid var(--au-border);
  }
  .au-overlay {
    position: absolute;
    inset: 0;
    width: 80px;
    height: 80px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--au-card) 80%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .au-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 86px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: var(--au-text-secondary);
    background: var(--au-upload-bg);
    border: 1px solid var(--au-upload-border);
    cursor: pointer;
    transition: all 0.12s ease;
    letter-spacing: 0.2px;
  }
  .au-btn:hover {
    border-color: var(--au-border-strong);
    color: var(--au-text);
  }
</style>
