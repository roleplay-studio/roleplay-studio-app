<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, API_BASE, type Persona } from '../api';
  import { currentLang, t } from '../i18n';
  import { Input, Loading, Textarea } from '../ui';

  let lang = $state('en');
  let unsubLang: (() => void) | undefined;

  let personas = $state<Persona[]>([]);
  let showModal = $state(false);
  let editingId = $state<null | number>(null);
  let editName = $state('');
  let editDesc = $state('');
  let editAvatarPath = $state('');
  let editAvatarPreview = $state('');
  let uploading = $state(false);

  // Delete confirm
  let deletingId = $state<null | number>(null);

  onMount(() => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    load();
  });

  onDestroy(() => {
    unsubLang?.();
  });

  async function load() {
    try {
      personas = await api.listPersonas();
    } catch (e) {
      console.error('Failed to load personas:', e);
    }
  }

  function openCreate() {
    editingId = null;
    editName = '';
    editDesc = '';
    editAvatarPath = '';
    editAvatarPreview = '';
    showModal = true;
  }

  function openEdit(p: Persona) {
    editingId = p.id;
    editName = p.name;
    editDesc = p.description;
    editAvatarPath = p.avatar_path || '';
    editAvatarPreview = avatarUrl(p.avatar_path) || '';
    showModal = true;
  }

  function closeModal() {
    showModal = false;
  }

  function avatarUrl(path: null | string): null | string {
    if (!path) return null;
    return `${API_BASE}${path}`;
  }

  async function handleAvatarUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    uploading = true;
    try {
      const path = await api.uploadPersonaAvatar(file);
      editAvatarPath = path;
      editAvatarPreview = `${API_BASE}${path}`;
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Failed to upload avatar');
    } finally {
      uploading = false;
    }
  }

  async function save() {
    const body = {
      avatar_path: editAvatarPath || null,
      description: editDesc.trim(),
      name: editName.trim(),
    };
    try {
      if (editingId) {
        await api.updatePersona(editingId, body);
      } else {
        await api.createPersona(body);
      }
      closeModal();
      await load();
    } catch (e) {
      console.error('Save failed:', e);
    }
  }

  function confirmDelete(id: number) {
    deletingId = id;
  }

  async function doDelete() {
    if (deletingId === null) return;
    try {
      await api.deletePersona(deletingId);
      deletingId = null;
      await load();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  function cancelDelete() {
    deletingId = null;
  }
</script>

<div class="pp-page">
  <!-- Header -->
  <header class="pp-header">
    <div>
      <h1 class="pp-title">{t('personas.title', lang)}</h1>
      <p class="pp-subtitle">{t('personas.subtitle', lang)}</p>
    </div>
    <button class="ray-btn primary" onclick={openCreate}>
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        ><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"
        ></line></svg
      >
      {t('personas.new', lang)}
    </button>
  </header>

  {#if personas.length === 0}
    <div class="pp-empty">
      <svg class="pp-empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.5"
          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
        />
      </svg>
      <p class="pp-empty-title">{t('personas.no_personas', lang)}</p>
      <p class="pp-empty-hint">{t('personas.no_personas_hint', lang)}</p>
    </div>
  {:else}
    <div class="pp-grid">
      {#each personas as p (p.id)}
        <div class="pp-card">
          <div class="pp-card-top">
            <div class="pp-card-info">
              {#if p.avatar_path}
                <img src={avatarUrl(p.avatar_path)} alt={p.name} class="pp-avatar" />
              {:else}
                <div class="pp-avatar-placeholder">
                  {p.name[0]?.toUpperCase() || '?'}
                </div>
              {/if}
              <div>
                <h3 class="pp-name">{p.name}</h3>
                <p class="pp-desc">{p.description || t('personas.no_description', lang)}</p>
              </div>
            </div>
            <div class="pp-actions">
              <button
                class="pp-action-btn"
                onclick={() => openEdit(p)}
                title={t('personas.edit_title_tooltip', lang)}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path><path
                    d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                  ></path></svg
                >
              </button>
              <button
                class="pp-action-btn danger"
                onclick={() => confirmDelete(p.id)}
                title={t('personas.delete_title_tooltip', lang)}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><polyline points="3 6 5 6 21 6"></polyline><path
                    d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
                  ></path></svg
                >
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Modal -->
{#if showModal}
  <div class="pm-overlay" onclick={closeModal} role="presentation"></div>
  <div class="pm-modal">
    <div class="pm-header">
      <h3 class="pm-title">
        {editingId ? t('personas.edit_title', lang) : t('personas.new_title', lang)}
      </h3>
      <button class="pm-close" onclick={closeModal}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"
          ></line></svg
        >
      </button>
    </div>
    <div class="pm-body">
      <div class="pm-avatar-row">
        <div class="pm-avatar-wrap">
          {#if editAvatarPreview}
            <img src={editAvatarPreview} alt="avatar" class="pm-avatar-img" />
          {:else}
            <div class="pm-avatar-placeholder">
              {(editName || '?')[0].toUpperCase()}
            </div>
          {/if}
          {#if uploading}
            <div class="pm-avatar-overlay">
              <Loading size="sm" type="dots" />
            </div>
          {/if}
        </div>
        <label class="pm-upload-btn">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline
              points="17 8 12 3 7 8"
            ></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg
          >
          {t('personas.upload_avatar', lang)}
          <input type="file" accept="image/*" class="hidden" onchange={handleAvatarUpload} />
        </label>
      </div>
      <div class="pm-fields">
        <div class="field-group">
          <label class="field-label">{t('personas.name', lang)}</label>
          <Input bind:value={editName} placeholder={t('personas.name_placeholder', lang)} />
        </div>
        <div class="field-group">
          <label class="field-label">{t('personas.description', lang)}</label>
          <Textarea
            bind:value={editDesc}
            rows={10}
            placeholder={t('personas.description_placeholder', lang)}
          />
        </div>
      </div>
    </div>
    <div class="pm-footer">
      <button class="ray-btn" onclick={closeModal}>{t('personas.cancel', lang)}</button>
      <button class="ray-btn primary" onclick={save}
        >{editingId ? t('personas.save', lang) : t('personas.create', lang)}</button
      >
    </div>
  </div>
{/if}

<!-- Delete confirm -->
{#if deletingId !== null}
  <div class="pm-overlay" onclick={cancelDelete} role="presentation"></div>
  <div class="pm-modal pm-del-modal">
    <div class="pm-del-icon">
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
          d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        ></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"
        ></line></svg
      >
    </div>
    <p class="pm-del-msg">{t('personas.delete_confirm', lang)}</p>
    <div class="pm-del-actions">
      <button class="ray-btn" onclick={cancelDelete}>{t('personas.cancel', lang)}</button>
      <button class="ray-btn danger" onclick={doDelete}>{t('common.delete', lang)}</button>
    </div>
  </div>
{/if}

<style>
  :root {
    --pp-bg-card: #ffffff;
    --pp-border: rgba(0, 0, 0, 0.06);
    --pp-border-strong: rgba(0, 0, 0, 0.1);
    --pp-text: #1d1d1f;
    --pp-text-secondary: #6e6e73;
    --pp-text-tertiary: #86868b;
    --pp-hover: rgba(0, 0, 0, 0.04);
    --pp-red: #ff3b30;
    --pp-blue: hsl(211, 100%, 50%);
    --pp-shadow-ring: rgba(0, 0, 0, 0.04);
    --pp-shadow-inset: rgba(0, 0, 0, 0.02);
    --pp-overlay: #ffffff;
    --pp-bg: #f5f5f7;
  }
  :root.dark {
    --pp-bg-card: #101111;
    --pp-border: rgba(255, 255, 255, 0.06);
    --pp-border-strong: rgba(255, 255, 255, 0.1);
    --pp-text: #f9f9f9;
    --pp-text-secondary: #9c9c9d;
    --pp-text-tertiary: #6a6b6c;
    --pp-hover: rgba(255, 255, 255, 0.04);
    --pp-red: #ff6363;
    --pp-blue: hsl(202, 100%, 67%);
    --pp-shadow-ring: rgb(27, 28, 30);
    --pp-shadow-inset: rgb(7, 8, 10);
    --pp-overlay: #1b1c1e;
    --pp-bg: #07080a;
  }
  .pp-page {
    padding: 32px 48px;
    color: var(--pp-text);
  }
  .pp-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 32px;
    gap: 16px;
    flex-wrap: wrap;
  }
  .pp-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 28px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--pp-text);
  }
  .pp-subtitle {
    font-family: 'Maple Mono', sans-serif;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--pp-text-secondary);
    margin: 4px 0 0;
  }
  .pp-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 80px 20px;
    background: var(--pp-bg-card);
    border: 1px solid var(--pp-border);
    border-radius: 12px;
    box-shadow:
      var(--pp-shadow-ring) 0px 0px 0px 1px,
      var(--pp-shadow-inset) 0px 0px 0px 1px inset;
  }
  .pp-empty-icon {
    width: 48px;
    height: 48px;
    color: var(--pp-text-tertiary);
    margin-bottom: 16px;
  }
  .pp-empty-title {
    font-size: 16px;
    font-weight: 500;
    color: var(--pp-text-secondary);
    margin-bottom: 4px;
    font-family: 'Maple Mono', sans-serif;
  }
  .pp-empty-hint {
    font-size: 13px;
    color: var(--pp-text-tertiary);
    font-family: 'Maple Mono', sans-serif;
  }
  .pp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 10px;
  }
  .pp-card {
    background: var(--pp-bg-card);
    border: 1px solid var(--pp-border);
    border-radius: 12px;
    padding: 16px;
    box-shadow:
      var(--pp-shadow-ring) 0px 0px 0px 1px,
      var(--pp-shadow-inset) 0px 0px 0px 1px inset;
    transition: all 0.15s ease;
  }
  .pp-card:hover {
    border-color: var(--pp-border-strong);
  }
  .pp-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  .pp-card-info {
    display: flex;
    gap: 12px;
    align-items: center;
    min-width: 0;
    flex: 1;
  }
  .pp-avatar {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    object-fit: cover;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  .pp-avatar-placeholder {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
    background: linear-gradient(135deg, #8b5cf6, #06b6d4);
  }
  .pp-name {
    font-family: 'Maple Mono', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--pp-text);
    letter-spacing: 0.2px;
    margin: 0 0 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pp-desc {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--pp-text-secondary);
    letter-spacing: 0.15px;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .pp-actions {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
  }
  .pp-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--pp-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .pp-action-btn:hover {
    background: var(--pp-hover);
    color: var(--pp-text);
  }
  .pp-action-btn.danger:hover {
    background: color-mix(in srgb, var(--pp-red) 10%, transparent);
    color: var(--pp-red);
  }

  /* ─── Modal ─── */
  .pm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(4px);
    z-index: 98;
  }
  .pm-modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--pp-overlay);
    border: 1px solid var(--pp-border);
    border-radius: 14px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.3);
    z-index: 99;
    width: 440px;
    max-width: 90vw;
    max-height: 85vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .pm-del-modal {
    width: 360px;
    padding: 24px;
    gap: 16px;
    align-items: center;
    text-align: center;
  }
  .pm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px 0;
  }
  .pm-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: var(--pp-text);
    margin: 0;
    letter-spacing: 0.2px;
  }
  .pm-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--pp-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .pm-close:hover {
    background: var(--pp-hover);
    color: var(--pp-text);
  }
  .pm-body {
    padding: 16px 20px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .pm-avatar-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .pm-avatar-wrap {
    position: relative;
    flex-shrink: 0;
  }
  .pm-avatar-img {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    object-fit: cover;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  .pm-avatar-placeholder {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    background: linear-gradient(135deg, #8b5cf6, #06b6d4);
  }
  .pm-avatar-overlay {
    position: absolute;
    inset: 0;
    border-radius: 12px;
    background: color-mix(in srgb, var(--pp-overlay) 70%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .pm-upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 12px;
    border-radius: 86px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: var(--pp-text-secondary);
    background: color-mix(in srgb, var(--pp-text) 4%, transparent);
    border: 1px solid var(--pp-border);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .pm-upload-btn:hover {
    border-color: var(--pp-border-strong);
    color: var(--pp-text);
  }
  .pm-fields {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field-label {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--pp-text-secondary);
    letter-spacing: 0.2px;
  }
  .pm-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 0 20px 16px;
  }
  .pm-del-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--pp-red) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--pp-red);
  }
  .pm-del-msg {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    color: var(--pp-text-secondary);
    margin: 0;
    line-height: 1.5;
  }
  .pm-del-actions {
    display: flex;
    gap: 8px;
    width: 100%;
  }
  .pm-del-actions .ray-btn {
    flex: 1;
    justify-content: center;
  }

  /* ─── Input/Textarea override ─── */
  :global(.pp-page .input),
  :global(.pp-page .textarea) {
    background: var(--pp-bg) !important;
    border: 1px solid var(--pp-border) !important;
    border-radius: 8px !important;
    color: var(--pp-text) !important;
    font-family: 'Maple Mono', sans-serif !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    letter-spacing: 0.2px;
    box-shadow: none !important;
    transition: border-color 0.15s ease !important;
  }
  :global(.pp-page .input:focus),
  :global(.pp-page .textarea:focus) {
    border-color: var(--pp-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--pp-blue) 8%, transparent) !important;
  }
  :global(.pp-page .input::placeholder),
  :global(.pp-page .textarea::placeholder) {
    color: var(--pp-text-tertiary) !important;
  }

  @media (max-width: 768px) {
    .pp-page {
      padding: 20px 16px;
    }
    .pp-header {
      flex-direction: column;
    }
    .pp-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
