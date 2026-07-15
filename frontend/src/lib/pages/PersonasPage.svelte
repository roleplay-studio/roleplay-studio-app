<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, API_BASE, type Persona } from '../api';
  import { currentLang, t } from '../i18n';
  import { Button, GeneratedAvatar, Input, Loading, Modal, Textarea } from '../ui';

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
  let deletingName = $state('');
  // Derived boolean for the delete-confirm dialog (Modal wants a
  // bindable bool, not a nullable id).
  let deleteDialogOpen = $derived(deletingId !== null);

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

  function confirmDelete(id: number, name: string) {
    deletingId = id;
    deletingName = name;
  }

  async function doDelete() {
    if (deletingId === null) return;
    try {
      await api.deletePersona(deletingId);
      deletingId = null;
      deletingName = '';
      await load();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  function cancelDelete() {
    deletingId = null;
    deletingName = '';
  }
</script>

<div class="pp-page">
  <!-- Header -->
  <header class="pp-header">
    <div>
      <h1 class="pp-title">{t('personas.title', lang)}</h1>
      <p class="pp-subtitle">{t('personas.subtitle', lang)}</p>
    </div>
    <Button variant="primary" size="md" onclick={openCreate}>
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="12" y1="5" x2="12" y2="20"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
      {t('personas.new', lang)}
    </Button>
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
        <!-- The whole card is clickable → opens the edit modal
             (mirrors BotCard's bc-clickable affordance). Action
             buttons stopPropagation so e.g. delete fires on the
             btn, not the card.                                  -->
        <article
          class="pp-card pp-clickable"
          role="button"
          tabindex="0"
          onclick={() => openEdit(p)}
          onkeydown={(e) => e.key === 'Enter' && openEdit(p)}
        >
          <!-- Hero (avatar, square 180px) -->
          <div class="pp-hero">
            {#if p.avatar_path}
              <img src={avatarUrl(p.avatar_path)} alt={p.name} class="pp-hero-img" />
            {:else}
              <div class="pp-hero-placeholder">
                <GeneratedAvatar name={p.name} shape="square" block />
              </div>
            {/if}
            <div class="pp-hero-overlay"></div>
            <!-- Default/badge placeholder for future "type" tag -->
            <span class="pp-hero-type">Persona</span>
            <!-- Name overlaid on hero -->
            <h3 class="pp-hero-name">{p.name}</h3>
          </div>

          <!-- Body -->
          <div class="pp-body">
            <p class="pp-desc">{p.description || t('personas.no_description', lang)}</p>
            <div class="pp-footer">
              <span class="pp-meta">
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                Persona
              </span>
              <div class="pp-actions">
                <button
                  class="pp-action-btn"
                  onclick={(e) => {
                    e.stopPropagation();
                    openEdit(p);
                  }}
                  aria-label={t('personas.edit_title_tooltip', lang)}
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
                  >
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                </button>
                <button
                  class="pp-action-btn danger"
                  onclick={(e) => {
                    e.stopPropagation();
                    confirmDelete(p.id, p.name);
                  }}
                  aria-label={t('personas.delete_title_tooltip', lang)}
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
                  >
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path
                      d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
                    ></path>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<!-- Modal: create / edit -->
<Modal
  bind:open={showModal}
  size="md"
  title={editingId ? t('personas.edit_title', lang) : t('personas.new_title', lang)}
>
  <div class="pp-avatar-row">
    <div class="pp-avatar-wrap">
      {#if editAvatarPreview}
        <img src={editAvatarPreview} alt="avatar" class="pp-avatar-img" />
      {:else}
        <div class="pp-avatar-placeholder-modal">
          {#if editName}
            <GeneratedAvatar name={editName} shape="square" block />
          {:else}
            <span>?</span>
          {/if}
        </div>
      {/if}
      {#if uploading}
        <div class="pp-avatar-overlay">
          <Loading size="sm" type="dots" />
        </div>
      {/if}
    </div>
    <label class="pp-upload-btn">
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      {t('personas.upload_avatar', lang)}
      <input type="file" accept="image/*" class="hidden" onchange={handleAvatarUpload} />
    </label>
  </div>
  <div class="pp-fields">
    <div class="pp-field-group">
      <label class="pp-field-label">{t('personas.name', lang)}</label>
      <Input bind:value={editName} placeholder={t('personas.name_placeholder', lang)} />
    </div>
    <div class="pp-field-group">
      <label class="pp-field-label">{t('personas.description', lang)}</label>
      <Textarea
        bind:value={editDesc}
        rows={10}
        placeholder={t('personas.description_placeholder', lang)}
      />
    </div>
  </div>

  {#snippet footer()}
    <Button variant="outline" onclick={closeModal}>{t('personas.cancel', lang)}</Button>
    <Button variant="primary" onclick={save}
      >{editingId ? t('personas.save', lang) : t('personas.create', lang)}</Button
    >
  {/snippet}
</Modal>

<!-- Delete confirm: lighter-weight modal -->
<Modal
  bind:open={deleteDialogOpen}
  size="sm"
  title={t('personas.delete_title', lang)}
>
  <div class="pp-del-body">
    <div class="pp-del-icon">
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        ></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
    </div>
    <p class="pp-del-msg">{t('personas.delete_confirm', lang)}</p>
    {#if deletingName}
      <p class="pp-del-name">«{deletingName}»</p>
    {/if}
  </div>

  {#snippet footer()}
    <Button variant="outline" onclick={cancelDelete}>{t('personas.cancel', lang)}</Button>
    <Button variant="error" onclick={doDelete}>{t('common.delete', lang)}</Button>
  {/snippet}
</Modal>

<style>
  /* ── Tokens: page-local aliases over the canonical --ray-* system.
   * Self-contained: doesn't rely on .dark class for theming, uses
   * prefers-color-scheme for light fallback. This avoids overriding
   * --ray-* globally and keeps the page opt-in to future palette
   * changes via app.css.                                              */
  :root {
    --pp-bg-card: #ffffff;
    --pp-border: rgba(0, 0, 0, 0.06);
    --pp-border-strong: rgba(0, 0, 0, 0.1);
    --pp-border-subtle: rgba(0, 0, 0, 0.04);
    --pp-text: #1d1d1f;
    --pp-text-secondary: #6e6e73;
    --pp-text-tertiary: #86868b;
    --pp-hover: rgba(0, 0, 0, 0.03);
    --pp-red: #ff3b30;
    --pp-shadow-ring: rgba(0, 0, 0, 0.04);
    --pp-shadow-inset: rgba(0, 0, 0, 0.02);
  }
  :root.dark {
    --pp-bg-card: #101111;
    --pp-border: rgba(255, 255, 255, 0.06);
    --pp-border-strong: rgba(255, 255, 255, 0.1);
    --pp-border-subtle: rgba(255, 255, 255, 0.04);
    --pp-text: #f9f9f9;
    --pp-text-secondary: #9c9c9d;
    --pp-text-tertiary: #6a6b6c;
    --pp-hover: rgba(255, 255, 255, 0.03);
    --pp-red: #ff6363;
    --pp-shadow-ring: rgb(27, 28, 30);
    --pp-shadow-inset: rgb(7, 8, 10);
  }

  /* ── Page chrome ───────────────────────────────────────────── */
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

  /* ── Empty state ───────────────────────────────────────────── */
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

  /* ── Card grid ─────────────────────────────────────────────── */
  .pp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  /* ── Card (BotCard-style: hero, body, footer) ──────────────── */
  .pp-card {
    background: var(--pp-bg-card);
    border: 1px solid var(--pp-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow:
      var(--pp-shadow-ring) 0px 0px 0px 1px,
      var(--pp-shadow-inset) 0px 0px 0px 1px inset;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
  }
  /* Click-to-edit affordance — same cursor:focus pattern as BotCard.
     Focus ring matches the canonical --ray-blue focus indicator.   */
  .pp-card.pp-clickable {
    cursor: pointer;
    outline: none;
  }
  .pp-card.pp-clickable:focus-visible {
    border-color: var(--pp-border-strong);
    box-shadow:
      var(--pp-shadow-ring) 0px 0px 0px 1px,
      var(--pp-shadow-inset) 0px 0px 0px 1px inset,
      0 0 0 3px color-mix(in srgb, hsl(202, 100%, 67%) 8%, transparent);
  }
  .pp-card:hover {
    border-color: var(--pp-border-strong);
    box-shadow:
      var(--pp-shadow-ring) 0px 0px 0px 1px,
      var(--pp-shadow-inset) 0px 0px 0px 1px inset,
      0 8px 24px color-mix(in srgb, #000 8%, transparent);
    transform: translateY(-1px);
  }

  /* Hero — square, 180px tall, accommodates big avatars like BotCard */
  .pp-hero {
    position: relative;
    width: 100%;
    height: 180px;
    background: color-mix(in srgb, var(--pp-text) 3%, transparent);
  }
  .pp-hero-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }
  .pp-card:hover .pp-hero-img {
    transform: scale(1.03);
  }
  .pp-hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  /* Soft bottom-up fade so the overlaid name is always legible
     regardless of avatar brightness (matches BotCard). */
  .pp-hero-overlay {
    position: absolute;
    bottom: -10px;
    left: 0;
    right: 0;
    height: 60%;
    background: linear-gradient(to top, var(--pp-bg-card) 20%, transparent);
    pointer-events: none;
  }
  /* "Persona" tag in the upper-right corner — uses the same
     glass-pill style as BotCard's bc-hero-type, anchored to the
     design system. Future "type" variants (Owner / Starred /
     Custom) can reuse this slot. */
  .pp-hero-type {
    position: absolute;
    top: 8px;
    right: 10px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--pp-bg-card) 75%, transparent);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    letter-spacing: 0.3px;
    color: var(--pp-text-secondary);
  }
  .pp-hero-name {
    position: absolute;
    bottom: 10px;
    left: 12px;
    right: 12px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--pp-text);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Body — description + footer (matches BotCard internal padding) */
  .pp-body {
    padding: 12px 14px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
  }
  .pp-desc {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--pp-text-secondary);
    letter-spacing: 0.15px;
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    flex: 1;
  }
  .pp-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 8px;
    border-top: 1px solid var(--pp-border-subtle);
    gap: 8px;
  }
  .pp-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--pp-text-tertiary);
    letter-spacing: 0.2px;
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
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--pp-text-secondary);
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .pp-action-btn:hover {
    background: var(--pp-hover);
    color: var(--pp-text);
  }
  .pp-action-btn.danger:hover {
    background: color-mix(in srgb, var(--pp-red) 10%, transparent);
    color: var(--pp-red);
  }

  /* ── Modal internals (avatar row, fields) ──────────────────── */
  .pp-avatar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }
  .pp-avatar-wrap {
    position: relative;
    flex-shrink: 0;
  }
  .pp-avatar-img {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    object-fit: cover;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  /* Square GeneratedAvatar block inside modal — matches the modal
     64x64 frame so the user sees the same generated face as the
     card hero. */
  .pp-avatar-placeholder-modal {
    width: 64px;
    height: 64px;
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Maple Mono', sans-serif;
    font-size: 24px;
    font-weight: 700;
    color: var(--pp-text-tertiary);
    background: color-mix(in srgb, var(--pp-text) 5%, transparent);
  }
  .pp-avatar-overlay {
    position: absolute;
    inset: 0;
    border-radius: 12px;
    background: color-mix(in srgb, var(--pp-bg-card) 70%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .pp-upload-btn {
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
  .pp-upload-btn:hover {
    border-color: var(--pp-border-strong);
    color: var(--pp-text);
  }
  .pp-fields {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .pp-field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .pp-field-label {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--pp-text-secondary);
    letter-spacing: 0.2px;
  }

  /* ── Delete confirm (Modal size=sm) ────────────────────────── */
  .pp-del-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
    padding: 4px 0;
  }
  .pp-del-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--pp-red) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--pp-red);
  }
  .pp-del-msg {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    color: var(--pp-text-secondary);
    margin: 0;
    line-height: 1.5;
    max-width: 320px;
  }
  .pp-del-name {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--pp-text);
    margin: 0;
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