<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { SvelteMap } from 'svelte/reactivity';

  import {
    api,
    API_BASE,
    type Bot,
    BOT_TYPES,
    type BotType,
    type KnowledgeEntry,
    type SkillDTO,
  } from '../api';
  import AvatarUpload from '../AvatarUpload.svelte';
  import CategoryPicker from '../CategoryPicker.svelte';
  import SkillPicker from '../SkillPicker.svelte';
  import { currentLang, t } from '../i18n';
  import MarkdownRenderer from '../MarkdownRenderer.svelte';
  import { Input, Loading, Select, Tabs, Textarea } from '../ui';
  import { renderIcon } from '../ui/iconMap';
  import VersionsTimeline from '../ui/VersionsTimeline.svelte';
  import {
    canSortGreeting,
    loadGreetings,
    MAX_GREETINGS,
    saveGreetings,
    sortGreeting,
  } from '../utils/edit-greetings';
  import { parseMesExample } from '../utils/parseMesExample';
  import { serializeMesExample } from '../utils/serializeMesExample';

  const { botId = '0' }: { botId?: string } = $props();

  let bot: Bot | null = $state(null);
  let loading = $state(true);
  let saving = $state(false);
  let lang = $state('en');

  // Tabs
  let activeTab: 'edit' | 'knowledge' | 'prompts' | 'versions' = $state('edit');

  // Form fields
  let formName = $state('');
  let formPersonality = $state('');
  let formGreetings: string[] = $state(['']);
  let activeGreetingIndex = $state(0);
  let previewMode: Record<number, boolean> = $state({});
  // V1/V2/V3 character card `mes_example` (few-shot dialogue examples).
  // `formMesExample` is the canonical raw V2 string (the source of truth
  // sent to the backend). `mesExampleOpen` controls whether the editor
  // section is visible; collapsed when the value is empty.
  let formMesExample = $state('');
  let formDynamicSystemPrompt = $state('');
  let formWorldStatePrompt = $state('');
  let mesExampleOpen = $state(false);
  let mesExampleMode: 'raw' | 'visual' = $state('visual');
  let formScenario = $state('');
  let formDescription = $state('');
  let formAvatarPath = $state('');
  let formAvatarPreview = $state('');
  let formCategories: string[] = $state([]);
  let formBotType: BotType = $state('rp');
  let allCategories: string[] = $state([]);

  // Skills — Phase 6
  let formSkillIds: number[] = $state([]);
  let allSkills: SkillDTO[] = $state([]);
  let maxSkillsPerBot = 10;

  let uploading = $state(false);
  // Knowledge base
  let entries: KnowledgeEntry[] = $state([]);
  let newKnowledgeContent = $state('');
  let fileUploading = $state(false);
  let uploadResult = $state<null | { chunk_count: number; file_name: string }>(null);

  // Knowledge test search
  let testQuery = $state('');
  let testResults: { content: string; score: number }[] = $state([]);
  let testSearching = $state(false);
  const knowledgeThreshold = 0.25;

  function handleTestSearchKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTestSearch();
    }
  }

  async function handleTestSearch() {
    if (!bot || !testQuery.trim()) return;
    testSearching = true;
    testResults = [];
    try {
      const data = await api.testSearchKnowledge(bot.id, testQuery.trim(), 5);
      testResults = data.results || [];
    } catch (e) {
      console.error('Test search failed:', e);
    } finally {
      testSearching = false;
    }
  }

  onMount(async () => {
    currentLang.subscribe((v) => (lang = v));
    try {
      const id = parseInt(botId);
      if (id) {
        const [b, cats, kEntries, skills] = await Promise.all([
          api.getBot(id),
          api.categories(),
          api.listKnowledge(id),
          api.listSkills(),
        ]);
        bot = b;
        allCategories = cats;
        entries = kEntries;
        allSkills = skills;
        formSkillIds = b.skills ?? [];

        formName = b.name;
        formPersonality = b.personality;
        formGreetings = loadGreetings(b.first_message, b.alternate_greetings ?? []);
        activeGreetingIndex = 0;
        previewMode = {};
        formScenario = b.scenario;
        formDescription = b.description;
        formAvatarPath = b.avatar_path || '';
        formAvatarPreview = b.avatar_path ? API_BASE + b.avatar_path : '';
        formCategories = b.categories;
        formBotType = b.bot_type || 'rp';
        formMesExample = b.mes_example || '';
        mesExampleOpen = !!formMesExample;
        formDynamicSystemPrompt = b.dynamic_system_prompt || '';
        formWorldStatePrompt = b.world_state_prompt || '';
      }
    } catch (e) {
      console.error('Failed to load bot', e);
    } finally {
      loading = false;
    }

    await tick();
    document.querySelectorAll('textarea').forEach((ta) => {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
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

    await tick();
    document.querySelectorAll('textarea').forEach((ta) => {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
  }

  async function saveBot() {
    if (!formName.trim() || !formPersonality.trim()) return;
    if (formBotType === 'rp' && !formGreetings[0]?.trim()) return;
    if (!bot) return;

    saving = true;
    const { alternate_greetings, first_message } = saveGreetings(formGreetings);
    const payload = {
      alternate_greetings,
      avatar_path: formAvatarPath || null,
      bot_type: formBotType,
      categories: formCategories,
      description: formDescription || '',
      dynamic_system_prompt: formDynamicSystemPrompt || '',
      first_message,
      mes_example: formMesExample || '',
      name: formName,
      personality: formPersonality,
      scenario: formScenario || '',
      world_state_prompt: formWorldStatePrompt || '',
    };
    try {
      await api.updateBot(bot.id, payload);
      // Skill attachments go through their own endpoint
      // (Phase 6) — the bot-payload would otherwise have to encode
      // a list[int] which serialises as JSON inside a JSON body.
      // See api.updateBotSkills.
      await api.updateBotSkills(bot.id, formSkillIds);
      bot = await api.getBot(bot.id);
    } catch (e) {
      console.error('Save failed:', e);
    } finally {
      saving = false;
    }
  }

  async function addKnowledge() {
    if (!bot || !newKnowledgeContent.trim()) return;
    try {
      await api.addKnowledge(bot.id, newKnowledgeContent);
      newKnowledgeContent = '';
      entries = await api.listKnowledge(bot.id);
    } catch (e) {
      console.error('Add knowledge failed:', e);
    }
  }

  let editingEntryId: null | string = $state(null);
  let editingContent = $state('');

  function startEdit(entry: { content: string; id: string }) {
    editingEntryId = entry.id;
    editingContent = entry.content;
  }

  function cancelEdit() {
    editingEntryId = null;
    editingContent = '';
  }

  async function saveEdit() {
    if (!bot || !editingEntryId || !editingContent.trim()) return;
    try {
      await api.updateKnowledge(bot.id, editingEntryId, editingContent.trim());
      entries = await api.listKnowledge(bot.id);
      editingEntryId = null;
      editingContent = '';
    } catch (e) {
      console.error('Save edit failed:', e);
    }
  }

  async function removeKnowledge(entryId: string) {
    if (!bot) return;
    try {
      await api.deleteKnowledge(bot.id, entryId);
      entries = await api.listKnowledge(bot.id);
    } catch (e) {
      console.error('Remove knowledge failed:', e);
    }
  }

  async function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !bot) return;

    fileUploading = true;
    uploadResult = null;
    try {
      const result = await api.addKnowledgeFile(bot.id, file);
      uploadResult = { chunk_count: result.chunk_count, file_name: result.file_name };
      entries = await api.listKnowledge(bot.id);
    } catch (e) {
      console.error('File upload failed:', e);
      alert(`Upload failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      fileUploading = false;
      input.value = '';
    }
  }

  async function removeFile(fileName: string) {
    if (!bot) return;
    try {
      await api.deleteKnowledgeFile(bot.id, fileName);
      entries = await api.listKnowledge(bot.id);
    } catch (e) {
      console.error('Remove file failed:', e);
    }
  }

  // Greetings — unified tab list (index 0 is the bot's first message)

  function addGreeting() {
    if (formGreetings.length >= MAX_GREETINGS) return;
    formGreetings = [...formGreetings, ''];
    activeGreetingIndex = formGreetings.length - 1;
  }

  function removeGreeting(index: number) {
    // The first greeting (index 0) is the bot's first message — it cannot
    // be removed. The editor enforces ≥1 greeting for the editor to be
    // useful; saveBot rejects an empty first_message for RP bots.
    if (index === 0) return;
    formGreetings = formGreetings.filter((_, i) => i !== index);
    if (activeGreetingIndex >= formGreetings.length) {
      activeGreetingIndex = Math.max(0, formGreetings.length - 1);
    }
    // Drop preview state for removed index and shift higher indices down by 1.
    const next: Record<number, boolean> = {};
    for (const [k, v] of Object.entries(previewMode)) {
      const ki = Number(k);
      if (ki < index) next[ki] = v;
      else if (ki > index) next[ki - 1] = v;
    }
    previewMode = next;
  }

  function setActiveGreeting(id: string) {
    activeGreetingIndex = Number(id);
  }

  function toggleGreetingPreview(index: number) {
    previewMode = { ...previewMode, [index]: !previewMode[index] };
  }

  // ── mes_example (V1/V2/V3 few-shot dialogue examples) ──────────
  // All visual-mode mutations go through parse → mutate → serialize.
  // This is the "round-trip through structured form" pattern: even if
  // the user edits in visual mode, the raw string on save reflects
  // what the visual model produced (normalized to {{user}}:/{{char}}:).

  function addMesExampleDialogue() {
    const dialogues = parseMesExample(formMesExample);
    dialogues.push({ turns: [{ content: '', role: 'user' }] });
    formMesExample = serializeMesExample(dialogues);
  }

  function addMesExampleTurn(di: number) {
    const dialogues = parseMesExample(formMesExample);
    dialogues[di].turns.push({ content: '', role: 'char' });
    formMesExample = serializeMesExample(dialogues);
  }

  function removeMesExampleDialogue(di: number) {
    const dialogues = parseMesExample(formMesExample);
    dialogues.splice(di, 1);
    formMesExample = serializeMesExample(dialogues);
  }

  function removeMesExampleTurn(di: number, ti: number) {
    const dialogues = parseMesExample(formMesExample);
    dialogues[di].turns.splice(ti, 1);
    if (dialogues[di].turns.length === 0) {
      dialogues.splice(di, 1);
    }
    formMesExample = serializeMesExample(dialogues);
  }

  function moveMesExampleDialogue(di: number, dir: -1 | 1) {
    const dialogues = parseMesExample(formMesExample);
    const target = di + dir;
    if (target < 0 || target >= dialogues.length) return;
    [dialogues[di], dialogues[target]] = [dialogues[target], dialogues[di]];
    formMesExample = serializeMesExample(dialogues);
  }

  function updateMesExampleTurnContent(di: number, ti: number, content: string) {
    const dialogues = parseMesExample(formMesExample);
    dialogues[di].turns[ti].content = content;
    formMesExample = serializeMesExample(dialogues);
  }

  function updateMesExampleTurnRole(di: number, ti: number, role: 'char' | 'user') {
    const dialogues = parseMesExample(formMesExample);
    dialogues[di].turns[ti].role = role;
    formMesExample = serializeMesExample(dialogues);
  }

  function updateGreetingText(index: number, value: string) {
    formGreetings = formGreetings.map((g, i) => (i === index ? value : g));
  }

  function moveGreeting(direction: 'down' | 'up') {
    if (!canSortGreeting(activeGreetingIndex, direction, formGreetings.length)) return;
    formGreetings = sortGreeting(formGreetings, activeGreetingIndex, direction);
    activeGreetingIndex = direction === 'up' ? activeGreetingIndex - 1 : activeGreetingIndex + 1;
  }

  // Group: files vs manual
  const fileGroups = $derived(() => {
    const groups = new SvelteMap<string, { count: number }>();
    for (const e of entries) {
      if (e.source_type === 'file' && e.file_name) {
        const existing = groups.get(e.file_name);
        if (existing) {
          existing.count++;
        } else {
          groups.set(e.file_name, { count: 1 });
        }
      }
    }
    return groups;
  });
  const manualEntries = $derived(entries.filter((e) => e.source_type !== 'file'));
  const allFileGroups = $derived(fileGroups());

  function getFileIcon(fileName: string): string {
    const ext = fileName.split('.').pop()?.toLowerCase() || '';
    if (ext === 'pdf') return '📄';
    if (ext === 'docx' || ext === 'doc') return '📝';
    if (ext === 'md') return '📋';
    return '📃';
  }

  function goBack() {
    window.location.hash = '#/bots';
  }
</script>

<div class="bot-edit-page">
  {#if loading}
    <div class="loading-wrap">
      <Loading size="lg" />
    </div>
  {:else if !bot}
    <div class="not-found">
      <p>{t('bot_edit.not_found', lang)}</p>
      <button class="ray-link" onclick={goBack}>{t('bot_edit.back_to_studio', lang)}</button>
    </div>
  {:else}
    <!-- Header -->
    <header class="edit-header">
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
          <h1 class="edit-title">{t('bot_edit.title_edit', lang).replace('{name}', bot.name)}</h1>
          <p class="edit-subtitle">{t('bot_edit.subtitle', lang)}</p>
        </div>
      </div>
      {#if activeTab === 'edit'}
        <button
          class="ray-btn primary"
          onclick={saveBot}
          disabled={saving ||
            !formName.trim() ||
            !formPersonality.trim() ||
            !formGreetings[0]?.trim()}
        >
          {#if saving}
            <span class="btn-spinner"></span>
          {/if}
          {t('bot_edit.save', lang)}
        </button>
      {/if}
    </header>

    <!-- Tabs -->
    <nav class="edit-tabs">
      <button
        class="edit-tab"
        class:active={activeTab === 'edit'}
        onclick={() => (activeTab = 'edit')}
      >
        <span class="tab-icon">⚙️</span>
        <span class="tab-label">{t('bot_edit.tab_config', lang)}</span>
      </button>
      <button
        class="edit-tab"
        class:active={activeTab === 'knowledge'}
        onclick={() => (activeTab = 'knowledge')}
      >
        <span class="tab-icon">📚</span>
        <span class="tab-label"
          >{t('bot_edit.tab_knowledge', lang)}{entries.length > 0
            ? ` (${entries.length})`
            : ''}</span
        >
      </button>
      <button
        class="edit-tab"
        class:active={activeTab === 'versions'}
        onclick={() => (activeTab = 'versions')}
      >
        <span class="tab-icon">🕒</span>
        <span class="tab-label">{t('bot_versions.title', lang)}</span>
      </button>
      <button
        class="edit-tab"
        class:active={activeTab === 'prompts'}
        onclick={() => (activeTab = 'prompts')}
        data-testid="bot-edit-tab-prompts"
      >
        <span class="tab-icon">✨</span>
        <span class="tab-label">{t('bot_edit.tab_prompts', lang)}</span>
        {#if formDynamicSystemPrompt.trim() || formWorldStatePrompt.trim()}
          <span class="tab-badge" aria-label="has custom prompts"></span>
        {/if}
      </button>
    </nav>

    <!-- Tab: Configuration -->
    {#if activeTab === 'edit'}
      <section class="edit-section">
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
              inputId="edit-avatar-upload"
              onupload={handleAvatarUpload}
            />
            <div class="flex-1">
              <div class="field-group">
                <label class="field-label">{t('bot_create.bot_name', lang)}</label>
                <Input bind:value={formName} placeholder={t('bot_edit.name_placeholder', lang)} />
              </div>
            </div>
          </div>

          <!-- Description -->
          <div class="field-group">
            <label class="field-label">{t('bot_create.description', lang)}</label>
            <Textarea
              bind:value={formDescription}
              hint={t('bot_edit.description_hint', lang)}
              placeholder={t('bot_edit.description_placeholder', lang)}
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
              placeholder={t('bot_edit.personality_placeholder', lang)}
            />
          </div>

          <!-- Scenario -->
          <div class="field-group">
            <label class="field-label">{t('bot_create.scenario', lang)}</label>
            <Textarea
              bind:value={formScenario}
              hint={t('bot_edit.scenario_hint', lang)}
              rows={6}
              placeholder={t('bot_edit.scenario_placeholder', lang)}
            />
          </div>

          <!-- Greetings — unified tab list (index 0 = first message) -->
          <div class="field-group">
            <div class="greetings-header">
              <label class="field-label">{t('bot_edit.greetings', lang)}</label>
              <span
                class="greetings-counter"
                class:greetings-counter-max={formGreetings.length >= MAX_GREETINGS}
              >
                {formGreetings.length} / {MAX_GREETINGS}
              </span>
            </div>

            {#if formGreetings.length === 0}
              <p class="greetings-empty">{t('bot_edit.greetings_empty_hint', lang)}</p>
            {:else}
              <div class="greetings-tabs-row">
                <div class="greetings-tabs-scroll">
                  <Tabs
                    activeTab={String(activeGreetingIndex)}
                    onchange={setActiveGreeting}
                    tabs={formGreetings.map((_g, i) => ({
                      id: String(i),
                      label: t('bot_edit.greeting_tab_label', lang, { n: i + 1 }),
                    }))}
                  />
                </div>
                <div class="greetings-tab-actions">
                  <button
                    class="greeting-sort"
                    type="button"
                    disabled={!canSortGreeting(activeGreetingIndex, 'up', formGreetings.length)}
                    aria-label={t('bot_edit.greeting_move_up_aria', lang)}
                    onclick={() => moveGreeting('up')}
                  >
                    {@html renderIcon('chevron-up', 14)}
                  </button>
                  <button
                    class="greeting-sort"
                    type="button"
                    disabled={!canSortGreeting(activeGreetingIndex, 'down', formGreetings.length)}
                    aria-label={t('bot_edit.greeting_move_down_aria', lang)}
                    onclick={() => moveGreeting('down')}
                  >
                    {@html renderIcon('chevron-down', 14)}
                  </button>
                  <button
                    class="greeting-remove"
                    type="button"
                    disabled={activeGreetingIndex === 0}
                    aria-label={t('bot_edit.greeting_remove_aria', lang)}
                    onclick={() => removeGreeting(activeGreetingIndex)}
                  >
                    {@html renderIcon('x', 14)}
                  </button>
                </div>
              </div>

              <div class="greeting-editor">
                <div class="greeting-toolbar">
                  <button
                    class="greeting-preview-toggle"
                    class:greeting-preview-active={!!previewMode[activeGreetingIndex]}
                    type="button"
                    aria-pressed={!!previewMode[activeGreetingIndex]}
                    aria-label={t('bot_edit.preview_toggle', lang)}
                    onclick={() => toggleGreetingPreview(activeGreetingIndex)}
                  >
                    {@html renderIcon(previewMode[activeGreetingIndex] ? 'eye-off' : 'eye', 14)}
                    <span>{t('bot_edit.preview_toggle', lang)}</span>
                  </button>
                </div>

                {#if previewMode[activeGreetingIndex]}
                  <div class="greeting-preview">
                    {#if formGreetings[activeGreetingIndex]?.trim()}
                      <MarkdownRenderer content={formGreetings[activeGreetingIndex]} />
                    {:else}
                      <p class="greeting-preview-empty">
                        {t('bot_edit.greeting_preview_empty', lang)}
                      </p>
                    {/if}
                  </div>
                {:else}
                  <Textarea
                    value={formGreetings[activeGreetingIndex] ?? ''}
                    oninput={(e) =>
                      updateGreetingText(
                        activeGreetingIndex,
                        (e.target as HTMLTextAreaElement).value,
                      )}
                    rows={5}
                    placeholder={t('bot_edit.greetings_placeholder', lang)}
                  />
                {/if}
              </div>
            {/if}

            <div class="greetings-footer">
              <button
                class="greeting-add"
                type="button"
                disabled={formGreetings.length >= MAX_GREETINGS}
                onclick={addGreeting}
              >
                {@html renderIcon('plus', 14)}
                <span>{t('bot_edit.greeting_add', lang)}</span>
              </button>
              {#if formGreetings.length >= MAX_GREETINGS}
                <span class="greetings-max-hint">{t('bot_edit.max_greetings_reached', lang)}</span>
              {:else}
                <span class="greetings-hint">{t('bot_edit.greetings_hint', lang)}</span>
              {/if}
            </div>
          </div>

          <!-- Categories -->
          <div class="field-group">
            <CategoryPicker
              {allCategories}
              selected={formCategories}
              onchange={(cats) => (formCategories = cats)}
            />
          </div>

          <!-- Skills — Phase 6 -->
          <div class="field-group">
            <SkillPicker
              allSkills={allSkills}
              attachedIds={formSkillIds}
              maxReached={formSkillIds.length >= maxSkillsPerBot}
              onchange={(ids) => (formSkillIds = ids)}
            />
          </div>
        </div>

        <!-- Section: Example dialogues (V1/V2/V3 mes_example) -->
        <div class="mes-section">
          <h3>{t('bot_edit.mes_example', lang)}</h3>
          {#if !mesExampleOpen && !formMesExample}
            <div class="mes-hidden">
              <button
                type="button"
                class="mes-add-btn"
                onclick={() => {
                  mesExampleOpen = true;
                  mesExampleMode = 'raw';
                }}
              >
                + {t('bot_edit.mes_example_add', lang)}
              </button>
            </div>
          {:else}
            {@const dialogues = parseMesExample(formMesExample)}
            <div class="mes-toolbar">
              <div class="mes-mode-toggle">
                <button
                  type="button"
                  class="mes-mode-btn"
                  class:mes-mode-active={mesExampleMode === 'raw'}
                  onclick={() => (mesExampleMode = 'raw')}
                  >{t('bot_edit.mes_example_mode_raw', lang)}</button
                >
                <button
                  type="button"
                  class="mes-mode-btn"
                  class:mes-mode-active={mesExampleMode === 'visual'}
                  onclick={() => {
                    if (mesExampleMode === 'visual') return;
                    if (formMesExample && parseMesExample(formMesExample).length === 0) {
                      alert(t('bot_edit.mes_example_empty_dialogue', lang));
                    }
                    mesExampleMode = 'visual';
                  }}>{t('bot_edit.mes_example_mode_visual', lang)}</button
                >
              </div>
              <button
                type="button"
                class="mes-remove-btn"
                onclick={() => {
                  if (confirm(t('bot_edit.mes_example_remove_all_confirm', lang))) {
                    formMesExample = '';
                    mesExampleOpen = false;
                  }
                }}>{t('bot_edit.mes_example_remove_all', lang)}</button
              >
            </div>

            {#if mesExampleMode === 'raw'}
              <textarea
                class="mes-raw-textarea"
                bind:value={formMesExample}
                rows="10"
                placeholder={t('bot_edit.mes_example_raw_hint', lang)}
              ></textarea>
            {:else}
              <div class="mes-visual">
                {#each dialogues as dialogue, di (di)}
                  <div class="mes-dialogue">
                    <div class="mes-dialogue-header">
                      <span>{t('bot_edit.mes_example_dialogue_n', lang)}{di + 1}</span>
                      <button
                        type="button"
                        class="mes-icon-btn"
                        aria-label={t('bot_edit.mes_example_dialogue_move_up', lang)}
                        disabled={di === 0}
                        onclick={() => moveMesExampleDialogue(di, -1)}>↑</button
                      >
                      <button
                        type="button"
                        class="mes-icon-btn"
                        aria-label={t('bot_edit.mes_example_dialogue_move_down', lang)}
                        disabled={di === dialogues.length - 1}
                        onclick={() => moveMesExampleDialogue(di, 1)}>↓</button
                      >
                      <button
                        type="button"
                        class="mes-icon-btn"
                        aria-label={t('bot_edit.mes_example_dialogue_remove', lang)}
                        onclick={() => removeMesExampleDialogue(di)}>×</button
                      >
                    </div>
                    {#each dialogue.turns as turn, ti (ti)}
                      <div class="mes-turn">
                        <select
                          class="mes-turn-role"
                          value={turn.role}
                          onchange={(e) =>
                            updateMesExampleTurnRole(
                              di,
                              ti,
                              e.currentTarget.value as 'char' | 'user',
                            )}
                        >
                          <option value="user">{t('bot_edit.mes_example_turn_user', lang)}</option>
                          <option value="char">{t('bot_edit.mes_example_turn_char', lang)}</option>
                        </select>
                        <textarea
                          class="mes-turn-content"
                          rows="2"
                          value={turn.content}
                          oninput={(e) =>
                            updateMesExampleTurnContent(di, ti, e.currentTarget.value)}
                        ></textarea>
                        <button
                          type="button"
                          class="mes-icon-btn"
                          aria-label={t('bot_edit.mes_example_turn_remove', lang)}
                          onclick={() => removeMesExampleTurn(di, ti)}>×</button
                        >
                      </div>
                    {/each}
                    <button type="button" class="mes-add-btn" onclick={() => addMesExampleTurn(di)}
                      >+ {t('bot_edit.mes_example_add_turn', lang)}</button
                    >
                  </div>
                {/each}
                <button type="button" class="mes-add-btn" onclick={addMesExampleDialogue}
                  >+ {t('bot_edit.mes_example_add_dialogue', lang)}</button
                >
              </div>
            {/if}
          {/if}
        </div>
      </section>
    {/if}

    <!-- Tab: Knowledge -->
    {#if activeTab === 'knowledge'}
      <section class="edit-section">
        <div class="ray-card">
          <div class="k-header">
            <div>
              <h2 class="section-title">{t('bot_edit.tab_knowledge', lang)}</h2>
              <p class="field-hint">{t('bot_edit.knowledge_attach_hint', lang)}</p>
            </div>
            {#if entries.length > 0}
              <span class="k-count"
                >{t('bot_edit.entries_count', lang).replace('{n}', String(entries.length))}</span
              >
            {/if}
          </div>

          <!-- Add entry -->
          <div class="k-add">
            <Textarea
              bind:value={newKnowledgeContent}
              rows={3}
              placeholder={t('bot_edit.enter_knowledge', lang)}
            />
            <div class="k-add-actions">
              <button class="ray-btn" onclick={addKnowledge} disabled={!newKnowledgeContent.trim()}>
                {t('bot_edit.add_entry', lang)}
              </button>
              <label class="k-file-label">
                <input
                  type="file"
                  accept=".txt,.md,.docx,.pdf"
                  onchange={handleFileUpload}
                  disabled={fileUploading}
                  class="k-file-input"
                />
                <span class="ray-btn" class:uploading={fileUploading}>
                  {#if fileUploading}
                    ⏳ {t('bot_edit.uploading', lang)}
                  {:else}
                    📁 {t('bot_edit.upload_file', lang)}
                  {/if}
                </span>
              </label>
            </div>
            <span class="k-file-hint">{t('bot_edit.supported_formats', lang)}</span>
          </div>

          <!-- Upload result -->
          {#if uploadResult}
            <div class="k-upload-ok">
              ✅ {t('bot_edit.uploaded', lang)
                .replace('{name}', uploadResult.file_name)
                .replace('{n}', String(uploadResult.chunk_count))}
            </div>
          {/if}

          <!-- Files -->
          {#if allFileGroups.size > 0}
            <div class="k-section">
              <p class="k-section-label">{t('bot_edit.section_files', lang)}</p>
              <div class="k-list">
                {#each [...allFileGroups.entries()] as [fileName, group] (fileName)}
                  <div class="k-file-entry">
                    <span class="k-file-icon">{getFileIcon(fileName)}</span>
                    <div class="k-file-info">
                      <span class="k-file-name">{fileName}</span>
                      <span class="k-file-chunks"
                        >{t('bot_edit.chunks', lang).replace('{n}', String(group.count))}</span
                      >
                    </div>
                    <button
                      class="ray-icon-btn danger"
                      onclick={() => removeFile(fileName)}
                      title={t('bot_edit.delete_file', lang)}
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
                {/each}
              </div>
            </div>
          {/if}

          <!-- Manual Entries -->
          <div class="k-section">
            <p class="k-section-label">{t('bot_edit.section_manual', lang)}</p>
            <div class="k-list">
              {#if manualEntries.length === 0}
                <div class="k-empty">
                  <svg class="k-empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.5"
                      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    />
                  </svg>
                  <p class="k-empty-title">{t('bot_edit.no_manual_entries', lang)}</p>
                  <p class="field-hint">{t('bot_edit.manual_entries_hint', lang)}</p>
                </div>
              {:else}
                {#each manualEntries as entry (entry.id)}
                  <div class="k-entry">
                    <div class="k-entry-body">
                      {#if editingEntryId === entry.id}
                        <Textarea bind:value={editingContent} rows={3} />
                        <div class="k-entry-edit-actions">
                          <button class="ray-btn" onclick={cancelEdit}
                            >{t('bot_edit.edit_cancel', lang)}</button
                          >
                          <button class="ray-btn primary" onclick={saveEdit}
                            >{t('bot_edit.edit_save', lang)}</button
                          >
                        </div>
                      {:else}
                        <p class="k-entry-text">{entry.content}</p>
                      {/if}
                    </div>
                    <div class="k-entry-actions">
                      {#if editingEntryId === entry.id}
                        <button class="ray-icon-btn" onclick={cancelEdit}>
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            ><line x1="18" y1="6" x2="6" y2="18"></line><line
                              x1="6"
                              y1="6"
                              x2="18"
                              y2="18"
                            ></line></svg
                          >
                        </button>
                      {:else}
                        <button class="ray-icon-btn" onclick={() => startEdit(entry)}>
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            ><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"
                            ></path><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                            ></path></svg
                          >
                        </button>
                        <button
                          class="ray-icon-btn danger"
                          onclick={() => removeKnowledge(entry.id)}
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
                      {/if}
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          </div>

          <!-- Test Search -->
          <div class="k-test">
            <h3 class="section-title">{t('bot_edit.test_search', lang)}</h3>
            <p class="field-hint">{t('bot_edit.test_search_hint', lang)}</p>
            <div class="k-test-row">
              <div class="flex-1">
                <div class="field-group">
                  <Input
                    bind:value={testQuery}
                    placeholder={t('bot_edit.search_placeholder', lang)}
                    oninput={handleTestSearchKeydown as any}
                  />
                </div>
              </div>
              <button
                class="ray-btn"
                onclick={handleTestSearch}
                disabled={testSearching || !testQuery.trim()}
              >
                {#if testSearching}
                  <span class="btn-spinner"></span>
                {/if}
                {t('bot_edit.search', lang)}
              </button>
            </div>

            {#if testResults.length > 0}
              <div class="k-test-results">
                {#each testResults as r, i (i)}
                  <div class="k-test-item">
                    <div
                      class="k-test-score"
                      class:pass={r.score >= knowledgeThreshold}
                      class:cut={r.score < knowledgeThreshold}
                    >
                      <span class="k-test-num">{r.score.toFixed(4)}</span>
                      <span class="k-test-badge"
                        >{r.score >= knowledgeThreshold ? 'pass' : 'cut'}</span
                      >
                    </div>
                    <p class="k-test-content">{r.content}</p>
                  </div>
                {/each}
              </div>
            {:else if testQuery && !testSearching}
              <p class="k-test-empty">{t('bot_edit.no_results', lang)}</p>
            {/if}
          </div>
        </div>
      </section>
    {:else if activeTab === 'prompts'}
      <!-- Tab: Advanced prompts. The two fields that control long-chat
           stability (floating system reminder) and per-message state
           snapshots (background state generation). Hidden behind a
           separate tab so the main config form stays focused on
           identity/persona/scenario; power-users opt in. -->
      <section class="edit-section">
        <div class="ray-card">
          <div class="prompts-intro">
            <p>{t('bot_edit.prompts_intro', lang)}</p>
          </div>

          <!-- Floating system prompt — injected right before the last
               user message on every request. Solves instruction drift
               in long chats where the bot stops following its
               personality after 100+ messages. -->
          <div class="field-group">
            <label class="field-label">{t('bot_edit.dynamic_system_prompt', lang)}</label>
            <Textarea
              bind:value={formDynamicSystemPrompt}
              hint={t('bot_edit.dynamic_system_prompt_hint', lang)}
              rows={4}
              placeholder={'e.g. Always stay in character. Speak only as {{char}}.'}
            />
          </div>

          <!-- World-state prompt — system prompt for the background
               task that updates Conversation.state. The bot author
               owns the output format (YAML, JSON, prose). Empty
               string = no background state generation. -->
          <div class="field-group">
            <label class="field-label">{t('bot_edit.world_state_prompt', lang)}</label>
            <Textarea
              bind:value={formWorldStatePrompt}
              rows={6}
              placeholder="e.g. Emit a YAML block with keys: location, time_of_day, present_characters."
            />
          </div>
        </div>
      </section>
    {:else if activeTab === 'versions'}
      <section class="edit-section">
        <div class="ray-card">
          {#if bot}
            <VersionsTimeline
              botId={Number(botId)}
              {bot}
              onAfterRestore={async () => {
                try {
                  bot = await api.getBot(bot!.id);
                } catch (e) {
                  console.error('Reload after restore failed:', e);
                }
              }}
            />
          {/if}
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  /* ─── Theme Variables ─── */
  :root {
    --ray-bg-card: #ffffff;
    --ray-border-card: rgba(0, 0, 0, 0.06);
    --ray-text: #1d1d1f;
    --ray-text-secondary: #6e6e73;
    --ray-text-tertiary: #86868b;
    --ray-bg-surface: #f5f5f7;
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
    --ray-bg-surface: #07080a;
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

  .bot-edit-page {
    padding: 32px 48px;
    max-width: 900px;
    color: var(--ray-text);
    margin: 0 auto;
  }

  /* ─── Loading / Not Found ─── */
  .loading-wrap {
    display: flex;
    justify-content: center;
    padding: 80px 0;
  }
  .not-found {
    text-align: center;
    padding: 80px 0;
    color: var(--ray-text-secondary);
    font-size: 16px;
  }
  .ray-link {
    background: none;
    border: none;
    color: var(--ray-blue);
    cursor: pointer;
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    margin-top: 8px;
  }
  .ray-link:hover {
    opacity: 0.7;
  }

  /* ─── Header ─── */
  .edit-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 32px;
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
  .edit-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 22px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--ray-text);
  }
  .edit-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--ray-text-secondary);
    margin: 2px 0 0;
  }

  /* ─── Tabs ─── */
  .edit-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 28px;
    background: var(--ray-bg-card);
    border: 1px solid var(--ray-border-card);
    border-radius: 10px;
    padding: 4px;
  }
  .edit-tab {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ray-text-secondary);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.2px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .edit-tab:hover {
    color: var(--ray-text);
    opacity: 0.8;
  }
  .edit-tab.active {
    background: var(--ray-surface-raised);
    color: var(--ray-text);
    box-shadow:
      color-mix(in srgb, var(--ray-text) 5%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 20%, transparent) 0px 1px 3px;
  }
  .tab-icon {
    font-size: 16px;
  }
  .tab-label {
    font-size: 14px;
  }

  /* Small dot on a tab indicates the bot has data in that section.
     Used for the Advanced prompts tab so a configured dynamic /
     world-state prompt is visible at a glance. */
  .tab-badge {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ray-accent, #8b5cf6);
    margin-left: 6px;
    flex-shrink: 0;
  }

  /* Tab intro paragraph — small lead-in copy that frames the two
     fields below it. Lives at the top of the Advanced prompts card
     so the operator knows what the tab is for before reading the
     form fields. */
  .prompts-intro p {
    font-size: 13px;
    line-height: 1.55;
    color: var(--ray-text-secondary);
    margin: 0 0 16px;
    padding: 12px 14px;
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 6%, transparent);
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--ray-accent, #8b5cf6) 14%, transparent);
  }

  /* ─── Section ─── */
  .edit-section {
    margin-bottom: 40px;
  }
  .section-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 0.2px;
    color: var(--ray-text);
    margin: 0 0 2px;
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
  .field-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 400;
    color: var(--ray-text-tertiary);
    letter-spacing: 0.2px;
    margin: 2px 0 0;
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

  /* ─── Knowledge Header ─── */
  .k-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
  }
  .k-count {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    background: color-mix(in srgb, var(--ray-text) 4%, transparent);
    border: 1px solid var(--ray-border-card);
    border-radius: 86px;
    padding: 3px 12px;
    letter-spacing: 0.2px;
    white-space: nowrap;
  }

  /* ─── Knowledge Add ─── */
  .k-add {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .k-add-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .k-file-label {
    cursor: pointer;
  }
  .k-file-input {
    display: none;
  }
  .k-file-label .ray-btn.uploading {
    opacity: 0.5;
    cursor: wait;
  }
  .k-file-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-tertiary);
  }
  .k-upload-ok {
    padding: 10px 14px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--ray-green) 10%, transparent);
    color: var(--ray-green);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
  }

  /* ─── Knowledge Sections ─── */
  .k-section {
    margin-top: 16px;
  }
  .k-section-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--ray-text-secondary);
    margin: 0 0 8px;
  }

  /* ─── File entries ─── */
  .k-file-entry {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 10px;
    transition: border-color 0.15s ease;
  }
  .k-file-entry:hover {
    border-color: var(--ray-border-card);
  }
  .k-file-icon {
    font-size: 20px;
    flex-shrink: 0;
  }
  .k-file-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .k-file-name {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .k-file-chunks {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-tertiary);
  }

  /* ─── Knowledge List ─── */
  .k-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .k-empty {
    text-align: center;
    padding: 32px 0;
  }
  .k-empty-icon {
    width: 40px;
    height: 40px;
    margin: 0 auto 12px;
    color: var(--ray-text-tertiary);
  }
  .k-empty-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--ray-text-secondary);
    margin-bottom: 4px;
  }

  .k-entry {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 12px 14px;
    background: color-mix(in srgb, var(--ray-text) 2%, transparent);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 10px;
    transition: border-color 0.15s ease;
  }
  .k-entry:hover {
    border-color: var(--ray-border-card);
  }
  .k-entry-body {
    flex: 1;
    min-width: 0;
  }
  .k-entry-text {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--ray-text);
    letter-spacing: 0.2px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .k-entry-edit-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 8px;
  }
  .k-entry-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
    padding-top: 2px;
  }

  .ray-icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--ray-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .ray-icon-btn:hover {
    background: color-mix(in srgb, var(--ray-text) 5%, transparent);
    color: var(--ray-text);
  }
  .ray-icon-btn.danger:hover {
    background: color-mix(in srgb, var(--ray-red) 10%, transparent);
    color: var(--ray-red);
  }

  /* ─── Test Search ─── */
  .k-test {
    border-top: 1px solid var(--ray-border-subtle);
    padding-top: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .k-test-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }
  .k-test-results {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }
  .k-test-item {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 10px 12px;
    background: color-mix(in srgb, var(--ray-text) 1.5%, transparent);
    border: 1px solid var(--ray-border-subtle);
    border-radius: 8px;
  }
  .k-test-score {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-width: 56px;
    flex-shrink: 0;
  }
  .k-test-score.pass {
    color: var(--ray-green);
  }
  .k-test-score.cut {
    color: var(--ray-red);
  }
  .k-test-num {
    font-family: 'Geist Mono', 'SF Mono', ui-monospace, monospace;
    font-size: 12px;
    font-weight: 500;
  }
  .k-test-badge {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 1px 6px;
    border-radius: 4px;
    background: color-mix(in srgb, currentColor 10%, transparent);
  }
  .k-test-content {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 400;
    color: var(--ray-text-secondary);
    letter-spacing: 0.2px;
    line-height: 1.5;
    margin: 0;
  }
  .k-test-empty {
    text-align: center;
    padding: 16px 0;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    color: var(--ray-text-tertiary);
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

  /* ─── Textarea override ─── */
  :global(.bot-edit-page .input),
  :global(.bot-edit-page .select),
  :global(.bot-edit-page .textarea) {
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
  :global(.bot-edit-page .input:focus),
  :global(.bot-edit-page .select:focus),
  :global(.bot-edit-page .textarea:focus) {
    border-color: var(--ray-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ray-blue) 8%, transparent) !important;
  }
  :global(.bot-edit-page .input::placeholder),
  :global(.bot-edit-page .textarea::placeholder) {
    color: var(--ray-text-tertiary) !important;
  }
  :global(.bot-edit-page .select) {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9c9d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px !important;
  }

  /* ─── Alternate Greetings tabs ─── */
  .greetings-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .greetings-counter {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    letter-spacing: 0.3px;
    color: var(--ray-text-tertiary, #6a6b6c);
    padding: 2px 8px;
    border-radius: 6px;
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 4%, transparent);
  }
  .greetings-counter.greetings-counter-max {
    color: var(--ray-red, #ff6363);
  }
  .greetings-empty {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text-tertiary, #6a6b6c);
    padding: 16px;
    border: 1px dashed var(--ray-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    margin: 0 0 10px 0;
    text-align: center;
  }
  .greetings-tabs-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .greetings-tabs-scroll {
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
  .greetings-tab-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .greeting-sort,
  .greeting-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    flex-shrink: 0;
    background: transparent;
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--ray-text-secondary, #9c9c9d);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .greeting-sort:hover:not(:disabled),
  .greeting-remove:hover:not(:disabled) {
    color: var(--ray-text, #f9f9f9);
    border-color: var(--ray-border-strong, rgba(255, 255, 255, 0.1));
  }
  .greeting-remove:hover:not(:disabled) {
    color: var(--ray-red, #ff6363);
    border-color: var(--ray-red, #ff6363);
    background: color-mix(in srgb, var(--ray-red, #ff6363) 8%, transparent);
  }
  .greeting-sort:disabled,
  .greeting-remove:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .greeting-editor {
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    background: var(--ray-bg, #07080a);
    overflow: hidden;
  }
  .greeting-toolbar {
    display: flex;
    justify-content: flex-end;
    padding: 6px 8px;
    border-bottom: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
  }
  .greeting-preview-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: transparent;
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 6px;
    color: var(--ray-text-secondary, #9c9c9d);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .greeting-preview-toggle:hover {
    color: var(--ray-text, #f9f9f9);
    border-color: var(--ray-border-card, rgba(255, 255, 255, 0.08));
  }
  .greeting-preview-toggle.greeting-preview-active {
    color: var(--ray-blue, hsl(202, 100%, 67%));
    border-color: var(--ray-blue, hsl(202, 100%, 67%));
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 8%, transparent);
  }
  .greeting-preview {
    padding: 14px 16px;
    min-height: 80px;
    max-height: 360px;
    overflow-y: auto;
    font-size: 13px;
    line-height: 1.55;
    color: var(--ray-text, #f9f9f9);
  }
  .greeting-preview-empty {
    color: var(--ray-text-tertiary, #6a6b6c);
    font-style: italic;
    margin: 0;
  }
  .greetings-footer {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
  }
  .greeting-add {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: transparent;
    border: 1px solid var(--ray-border-card, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--ray-text, #f9f9f9);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .greeting-add:hover:not(:disabled) {
    border-color: var(--ray-blue, hsl(202, 100%, 67%));
    color: var(--ray-blue, hsl(202, 100%, 67%));
  }
  .greeting-add:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .greetings-hint,
  .greetings-max-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-tertiary, #6a6b6c);
  }
  .greetings-max-hint {
    color: var(--ray-red, #ff6363);
  }

  /* ─── Responsive ─── */
  @media (max-width: 768px) {
    .bot-edit-page {
      padding: 20px 16px;
    }
    .edit-header {
      flex-direction: column;
      gap: 12px;
    }
    .avatar-row {
      flex-direction: column;
      align-items: center;
    }
    .k-test-row {
      flex-direction: column;
    }
    .greetings-tabs-row {
      flex-wrap: wrap;
    }
    /* Phase 3.3 — Mobile horizontal-scroll tabs with fade affordance.
       4 tabs (Config / Knowledge / Versions / Prompts) don't fit at
       390px without wrapping, and wrapping creates 2-3 rows that
       push the form content below the fold. horizontal-scroll keeps
       one row + a visual cue that more tabs exist off-screen. */
    .edit-tabs {
      flex-wrap: nowrap;
      overflow-x: auto;
      overflow-y: hidden;
      /* Bleed into page gutters so fade doesn't clip focus rings */
      margin: 0 -16px 28px;
      padding: 4px 16px;
      /* Right-edge fade — see Dashboard.svelte for the same pattern */
      -webkit-mask-image: linear-gradient(
        to right,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) calc(100% - 24px),
        rgba(0, 0, 0, 0) 100%
      );
      mask-image: linear-gradient(
        to right,
        rgba(0, 0, 0, 1) 0%,
        rgba(0, 0, 0, 1) calc(100% - 24px),
        rgba(0, 0, 0, 0) 100%
      );
      scrollbar-width: none; /* Firefox */
    }
    .edit-tabs::-webkit-scrollbar {
      display: none; /* Chromium / Safari */
    }
    .edit-tab {
      flex: 0 0 auto; /* override flex: 1 from desktop */
      min-width: 110px; /* ensure tap target is wide enough */
    }
  }

  /* ── mes_example editor section ─────────────────────────── */
  /* Nested sub-card sitting inside the main .ray-card.       *
   * Reads as a self-contained "advanced" block while still  *
   * inheriting the parent's surface as page background.     */
  .mes-section {
    margin-top: 4px;
    padding: 20px;
    background: var(--ray-surface-raised, #f5f5f7);
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.08));
    border-radius: 10px;
  }
  .mes-section h3 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--ray-text-secondary, #6e6e73);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .mes-hidden {
    display: flex;
    justify-content: flex-end;
  }
  .mes-add-btn {
    background: transparent;
    color: var(--ray-accent, #8b5cf6);
    border: 1px dashed var(--ray-accent, #8b5cf6);
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }
  .mes-add-btn:hover {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 10%, transparent);
  }
  .mes-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .mes-mode-toggle {
    display: flex;
    gap: 4px;
  }
  .mes-mode-btn {
    background: transparent;
    color: var(--ray-text-secondary, #6e6e73);
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }
  .mes-mode-btn.mes-mode-active {
    background: var(--ray-accent, #8b5cf6);
    color: #fff;
    border-color: var(--ray-accent, #8b5cf6);
  }
  .mes-raw-textarea {
    width: 100%;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 12px;
    padding: 8px;
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    border-radius: 4px;
    resize: vertical;
    box-sizing: border-box;
    background: var(--ray-surface, #fff);
    color: var(--ray-text, #1d1d1f);
  }
  .mes-visual {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .mes-dialogue {
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    border-radius: 6px;
    padding: 10px;
    background: var(--ray-surface, #fff);
  }
  .mes-dialogue-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .mes-dialogue-header span {
    font-size: 12px;
    font-weight: 600;
    flex: 1;
    color: var(--ray-text, #1d1d1f);
  }
  .mes-icon-btn {
    background: transparent;
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    border-radius: 3px;
    padding: 2px 8px;
    cursor: pointer;
    font-size: 12px;
    color: var(--ray-text, #1d1d1f);
  }
  .mes-icon-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .mes-icon-btn:hover:not(:disabled) {
    background: var(--ray-border, rgba(0, 0, 0, 0.05));
  }
  .mes-turn {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin-bottom: 4px;
  }
  .mes-turn-role {
    font-size: 12px;
    padding: 4px 6px;
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    border-radius: 3px;
    background: var(--ray-surface, #fff);
    color: var(--ray-text, #1d1d1f);
  }
  .mes-turn-content {
    flex: 1;
    font-size: 12px;
    padding: 4px 6px;
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.1));
    border-radius: 3px;
    resize: vertical;
    background: var(--ray-surface, #fff);
    color: var(--ray-text, #1d1d1f);
  }
  .mes-remove-btn {
    background: transparent;
    color: var(--ray-red, #ff3b30);
    border: 1px solid var(--ray-red, #ff3b30);
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }
  .mes-remove-btn:hover {
    background: color-mix(in srgb, var(--ray-red, #ff3b30) 10%, transparent);
  }
</style>
