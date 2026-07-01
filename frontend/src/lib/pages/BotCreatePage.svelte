<script lang="ts">
  import { onMount } from 'svelte';

  import { api, API_BASE, BOT_TYPES, type BotType } from '../api';
  import AvatarUpload from '../AvatarUpload.svelte';
  import CategoryPicker from '../CategoryPicker.svelte';
  import { currentLang, t } from '../i18n';
  import { Input, Select, Textarea } from '../ui';

  let lang = $state('en');
  let formName = $state('');
  let formPersonality = $state('');
  let formFirstMessage = $state('');
  let formScenario = $state('');
  let formDescription = $state('');
  let formAvatarPath = $state('');
  let formCategories: string[] = $state([]);
  let formAvatarPreview = $state('');
  let formBotType: BotType = $state('rp');
  let allCategories: string[] = $state([]);
  let uploading = $state(false);
  let saving = $state(false);

  onMount(async () => {
    currentLang.subscribe((v) => (lang = v));
    try {
      allCategories = await api.categories();
    } catch (e) {
      console.error('Failed to load categories', e);
    }
  });

  async function handleAvatarUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    uploading = true;
    try {
      const path = await api.uploadAvatar(file);
      formAvatarPath = path;
      formAvatarPreview = `${API_BASE}${path}`;
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Failed to upload avatar');
    } finally {
      uploading = false;
    }
  }

  async function createBot() {
    if (!formName.trim() || !formPersonality.trim()) return;
    if (formBotType === 'rp' && !formFirstMessage.trim()) return;

    saving = true;
    const payload = {
      avatar_path: formAvatarPath || null,
      bot_type: formBotType,
      categories: formCategories,
      description: formDescription || '',
      first_message: formFirstMessage,
      name: formName,
      personality: formPersonality,
      scenario: formScenario || '',
    };
    try {
      await api.createBot(payload);
      window.location.hash = '#/bots';
    } catch (e) {
      console.error('Create failed:', e);
    } finally {
      saving = false;
    }
  }

  function goBack() {
    window.location.hash = '#/bots';
  }
</script>

<div class="bot-create-page">
  <!-- Header -->
  <header class="create-header">
    <div class="header-left">
      <button class="ray-back-btn" onclick={goBack}>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg
        >
      </button>
      <div>
        <h1 class="create-title">{t('bot_create.title', lang)}</h1>
        <p class="create-subtitle">{t('bot_create.subtitle', lang)}</p>
      </div>
    </div>
    <button
      class="ray-btn primary"
      onclick={createBot}
      disabled={saving || !formName.trim() || !formPersonality.trim() || !formFirstMessage.trim()}
    >
      {#if saving}
        <span class="btn-spinner"></span>
      {/if}
      {t('common.create_bot', lang)}
    </button>
  </header>

  <section class="create-section">
    <div class="ray-card">
      <!-- Bot Type -->
      <div class="field-group">
        <label class="field-label">{t('bot_create.bot_type', lang)}</label>
        <Select
          bind:value={formBotType}
          options={BOT_TYPES.map((bt) => ({ label: bt.label, value: bt.value }))}
        />
      </div>

      <!-- Avatar + Name -->
      <div class="avatar-row">
        <AvatarUpload
          avatarPreview={formAvatarPreview}
          name={formName}
          {uploading}
          inputId="create-avatar-upload"
          onupload={handleAvatarUpload}
        />
        <div class="flex-1">
          <div class="field-group">
            <label class="field-label">{t('bot_create.bot_name', lang)}</label>
            <Input bind:value={formName} placeholder={t('bot_create.name_placeholder', lang)} />
          </div>
        </div>
      </div>

      <!-- Description -->
      <div class="field-group">
        <label class="field-label">{t('bot_create.description', lang)}</label>
        <Textarea
          bind:value={formDescription}
          hint={t('bot_create.description_hint', lang)}
          placeholder={t('bot_create.description_placeholder', lang)}
          rows={3}
        />
      </div>

      <!-- Personality -->
      <div class="field-group">
        <label class="field-label"
          >{t('bot_create.personality', lang)} <span class="required">*</span></label
        >
        <Textarea
          bind:value={formPersonality}
          required
          rows={5}
          placeholder={t('bot_create.personality_placeholder', lang)}
        />
      </div>

      <!-- Scenario -->
      <div class="field-group">
        <label class="field-label">{t('bot_create.scenario', lang)}</label>
        <Textarea
          bind:value={formScenario}
          hint={t('bot_create.scenario_hint', lang)}
          rows={6}
          placeholder={t('bot_create.scenario_placeholder', lang)}
        />
      </div>

      <!-- First message -->
      <div class="field-group">
        <label class="field-label"
          >{t('bot_create.first_message', lang)} <span class="required">*</span></label
        >
        <Textarea
          bind:value={formFirstMessage}
          required
          rows={4}
          placeholder={t('bot_create.first_message_placeholder', lang)}
        />
      </div>

      <!-- Categories -->
      <div class="field-group">
        <CategoryPicker
          {allCategories}
          selected={formCategories}
          onchange={(cats) => (formCategories = cats)}
        />
      </div>
    </div>
  </section>
</div>

<style>
  /* ─── Theme Variables ─── */
  :root {
    --ray-bg-card: #ffffff;
    --ray-border-card: rgba(0, 0, 0, 0.06);
    --ray-text: #1d1d1f;
    --ray-text-secondary: #6e6e73;
    --ray-text-tertiary: #86868b;
    --ray-border-strong: rgba(0, 0, 0, 0.1);
    --ray-border-subtle: rgba(0, 0, 0, 0.04);
    --ray-shadow-ring: rgba(0, 0, 0, 0.04);
    --ray-shadow-inset: rgba(0, 0, 0, 0.02);
    --ray-green: #34c759;
    --ray-red: #ff3b30;
    --ray-blue: hsl(211, 100%, 50%);
    --ray-upload-bg: rgba(0, 0, 0, 0.04);
    --ray-upload-border: rgba(0, 0, 0, 0.06);
    --ray-surface-raised: #f0f0f2;
    --ray-bg: #f5f5f7;
    --ray-overlay: #ffffff;
  }
  :root.dark {
    --ray-bg-card: #101111;
    --ray-border-card: rgba(255, 255, 255, 0.06);
    --ray-text: #f9f9f9;
    --ray-text-secondary: #9c9c9d;
    --ray-text-tertiary: #6a6b6c;
    --ray-border-strong: rgba(255, 255, 255, 0.1);
    --ray-border-subtle: rgba(255, 255, 255, 0.04);
    --ray-shadow-ring: rgb(27, 28, 30);
    --ray-shadow-inset: rgb(7, 8, 10);
    --ray-green: #5fc992;
    --ray-red: #ff6363;
    --ray-blue: hsl(202, 100%, 67%);
    --ray-upload-bg: rgba(255, 255, 255, 0.04);
    --ray-upload-border: rgba(255, 255, 255, 0.06);
    --ray-surface-raised: #1b1c1e;
    --ray-bg: #07080a;
    --ray-overlay: #1b1c1e;
  }

  .bot-create-page {
    padding: 32px 48px;
    max-width: 900px;
    color: var(--ray-text);
  }

  /* ─── Header ─── */
  .create-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 32px;
    gap: 16px;
  }
  .header-left {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .ray-back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--ray-border-card);
    border-radius: 8px;
    background: var(--ray-bg-card);
    color: var(--ray-text);
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .ray-back-btn:hover {
    border-color: var(--ray-border-strong);
    opacity: 0.7;
  }
  .create-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 22px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--ray-text);
  }
  .create-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary);
    margin: 2px 0 0;
  }

  /* ─── Section ─── */
  .create-section {
    margin-bottom: 40px;
  }

  /* ─── Raycast Card overrides ─── */
  .ray-card {
    padding: 24px;
    gap: 20px;
  }

  /* ─── Fields ─── */
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
  }
  .required {
    color: var(--ray-red);
    font-weight: 600;
  }

  /* ─── Avatar Row ─── */
  .avatar-row {
    display: flex;
    gap: 16px;
    align-items: flex-start;
  }
  .avatar-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  .avatar-label {
    cursor: pointer;
    position: relative;
    display: block;
  }
  .avatar-img {
    width: 80px;
    height: 80px;
    border-radius: 12px;
    object-fit: cover;
    box-shadow: 0 4px 12px color-mix(in srgb, #000 20%, transparent);
    border: 1px solid var(--ray-border-card);
  }
  .avatar-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    box-shadow: 0 4px 12px color-mix(in srgb, #000 20%, transparent);
  }
  .avatar-overlay {
    position: absolute;
    inset: 0;
    width: 80px;
    height: 80px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--ray-bg-card) 80%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .ray-upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 86px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    background: var(--ray-upload-bg);
    border: 1px solid var(--ray-upload-border);
    cursor: pointer;
    transition: all 0.15s ease;
    letter-spacing: 0.2px;
  }
  .ray-upload-btn:hover {
    border-color: var(--ray-border-strong);
    color: var(--ray-text);
  }

  /* ─── Categories ─── */
  .cat-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .cat-pill {
    padding: 5px 14px;
    border-radius: 86px;
    border: 1px solid var(--ray-border-card);
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .cat-pill:hover {
    border-color: var(--ray-border-strong);
    color: var(--ray-text);
  }
  .cat-pill.selected {
    background: color-mix(in srgb, var(--ray-blue) 12%, transparent);
    border-color: color-mix(in srgb, var(--ray-blue) 30%, transparent);
    color: var(--ray-blue);
  }

  /* ─── Raycast Buttons ─── */
  .ray-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 86px;
    background: transparent;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: opacity 0.15s ease;
    box-shadow:
      color-mix(in srgb, var(--ray-text) 10%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 3%, transparent) 0px 7px 3px;
    border: 1px solid var(--ray-border-strong);
  }
  .ray-btn:hover {
    opacity: 0.7;
  }
  .ray-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .ray-btn.primary {
    background: color-mix(in srgb, var(--ray-text) 8%, transparent);
    border-color: var(--ray-border-strong);
  }
  .ray-btn.primary:hover {
    opacity: 0.8;
  }

  .btn-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid color-mix(in srgb, var(--ray-text) 20%, transparent);
    border-top-color: var(--ray-text);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ─── Input/Textarea override ─── */
  :global(.bot-create-page .input),
  :global(.bot-create-page .select),
  :global(.bot-create-page .textarea) {
    background: var(--ray-bg) !important;
    border: 1px solid var(--ray-border-card) !important;
    border-radius: 8px !important;
    color: var(--ray-text) !important;
    font-family: 'Maple Mono', system-ui, sans-serif !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    letter-spacing: 0.2px;
    box-shadow: none !important;
    transition: border-color 0.15s ease !important;
  }
  :global(.bot-create-page .input:focus),
  :global(.bot-create-page .select:focus),
  :global(.bot-create-page .textarea:focus) {
    border-color: var(--ray-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue) 8%, transparent) !important;
  }
  :global(.bot-create-page .input::placeholder),
  :global(.bot-create-page .textarea::placeholder) {
    color: var(--ray-text-tertiary) !important;
  }
  :global(.bot-create-page .select) {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9c9d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px !important;
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .bot-create-page {
      padding: 20px 16px;
    }
    .create-header {
      flex-direction: column;
    }
    .avatar-row {
      flex-direction: column;
      align-items: center;
    }
  }
</style>
