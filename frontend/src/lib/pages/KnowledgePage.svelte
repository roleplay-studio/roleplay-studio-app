<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteMap } from 'svelte/reactivity';

  import { api, type Bot, type KnowledgeEntry } from '../api';
  import { currentLang, t } from '../i18n';
  import { Loading, Textarea } from '../ui';

  let lang = $state('en');
  onMount(() => currentLang.subscribe((v) => (lang = v)));
  let bots: Bot[] = $state([]);
  let selectedBotId: null | number = $state(null);
  let entries: KnowledgeEntry[] = $state([]);
  let loading = $state(true);
  let newContent = $state('');
  let uploading = $state(false);
  let uploadResult = $state<null | { chunk_count: number; file_name: string }>(null);

  onMount(async () => {
    try {
      bots = await api.listBots();
      if (bots.length > 0) {
        selectedBotId = bots[0].id;
        await loadEntries();
      }
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  });

  async function loadEntries() {
    if (!selectedBotId) return;
    try {
      entries = await api.listKnowledge(selectedBotId);
    } catch (e) {
      console.error(e);
    }
  }

  async function selectBot(id: number) {
    selectedBotId = id;
    await loadEntries();
  }

  async function addEntry() {
    if (!selectedBotId || !newContent.trim()) return;
    try {
      await api.addKnowledge(selectedBotId, newContent);
      newContent = '';
      await loadEntries();
    } catch (e) {
      console.error(e);
    }
  }

  async function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !selectedBotId) return;

    uploading = true;
    uploadResult = null;
    try {
      const result = await api.addKnowledgeFile(selectedBotId, file);
      uploadResult = { chunk_count: result.chunk_count, file_name: result.file_name };
      await loadEntries();
    } catch (e) {
      console.error(e);
      alert(`Upload failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      uploading = false;
      input.value = '';
    }
  }

  async function removeEntry(entryId: string) {
    if (!selectedBotId) return;
    try {
      await api.deleteKnowledge(selectedBotId, entryId);
      await loadEntries();
    } catch (e) {
      console.error(e);
    }
  }

  async function removeFile(fileName: string) {
    if (!selectedBotId) return;
    try {
      await api.deleteKnowledgeFile(selectedBotId, fileName);
      await loadEntries();
    } catch (e) {
      console.error(e);
    }
  }

  function getBotColor(botId: number): string {
    const colors = [
      'bg-indigo-400',
      'bg-sky-400',
      'bg-emerald-400',
      'bg-amber-400',
      'bg-rose-400',
      'bg-violet-400',
      'bg-cyan-400',
      'bg-pink-400',
      'bg-lime-400',
      'bg-orange-400',
    ];
    return colors[botId % colors.length];
  }

  // Group entries: files (by file_name) and manual entries
  const fileGroups = $derived(() => {
    const groups = new SvelteMap<string, { chunk_count: number; entries: KnowledgeEntry[] }>();
    for (const entry of entries) {
      if (entry.source_type === 'file' && entry.file_name) {
        const existing = groups.get(entry.file_name);
        if (existing) {
          existing.entries.push(entry);
          existing.chunk_count = (existing.chunk_count || 0) + 1;
        } else {
          groups.set(entry.file_name, { chunk_count: 1, entries: [entry] });
        }
      }
    }
    return groups;
  });

  const manualEntries = $derived(entries.filter((e) => e.source_type !== 'file'));
  const fileEntries = $derived(fileGroups());

  const selectedBot = $derived(bots.find((b) => b.id === selectedBotId));

  function getFileIcon(fileName: string): string {
    const ext = fileName.split('.').pop()?.toLowerCase() || '';
    if (ext === 'pdf') return '📄';
    if (ext === 'docx' || ext === 'doc') return '📝';
    if (ext === 'md') return '📋';
    return '📃';
  }
</script>

<div class="kp-page">
  <header class="kp-header">
    <div>
      <h1 class="kp-title">{t('knowledge.title', lang)}</h1>
      <p class="kp-subtitle">{t('knowledge.subtitle', lang)}</p>
    </div>
  </header>

  {#if loading}
    <div class="kp-loading"><Loading size="lg" /></div>
  {:else}
    <div class="kp-layout">
      <!-- Bot selector sidebar -->
      <aside class="kp-sidebar">
        <p class="kp-sidebar-label">{t('knowledge.filter', lang)}</p>
        <div class="kp-bot-list">
          {#each bots as bot (bot.id)}
            <button
              class="kp-bot-btn"
              class:selected={selectedBotId === bot.id}
              onclick={() => selectBot(bot.id)}
            >
              <span class="kp-bot-dot {getBotColor(bot.id)}"></span>
              <span class="kp-bot-name">{bot.name}</span>
            </button>
          {/each}
        </div>
      </aside>

      <!-- Entries -->
      <div class="kp-main">
        {#if selectedBot}
          <div class="kp-bar">
            <span class="kp-bar-info">
              {t('knowledge.entries_for', lang)
                .replace('{n}', String(entries.length))
                .replace('{name}', selectedBot.name)}
            </span>
          </div>

          <!-- Add entry -->
          <div class="kp-add-row">
            <div class="kp-add-input">
              <Textarea
                bind:value={newContent}
                rows={2}
                placeholder="Enter knowledge content..."
                resize="none"
              />
            </div>
            <button class="ray-btn primary" onclick={addEntry} disabled={!newContent.trim()}>
              + {t('knowledge.add', lang)}
            </button>
          </div>

          <!-- File upload -->
          <div class="kp-upload-row">
            <label class="kp-upload-label">
              <input
                type="file"
                accept=".txt,.md,.docx,.pdf"
                onchange={handleFileUpload}
                disabled={uploading}
                class="kp-upload-input"
              />
              <span class="kp-upload-btn" class:uploading>
                {#if uploading}
                  ⏳ Uploading...
                {:else}
                  📁 Upload File
                {/if}
              </span>
            </label>
            <span class="kp-upload-hint">Supported: .txt, .md, .docx, .pdf</span>
          </div>

          <!-- Upload result -->
          {#if uploadResult}
            <div class="kp-upload-result">
              ✅ Uploaded <strong>{uploadResult.file_name}</strong> — {uploadResult.chunk_count} chunks
              created
            </div>
          {/if}

          <!-- Files list -->
          {#if fileEntries.size > 0}
            <div class="kp-section">
              <p class="kp-section-title">{t('knowledge.section_files', lang)}</p>
              <div class="kp-list">
                {#each [...fileEntries.entries()] as [fileName, group] (fileName)}
                  <div class="kp-file-entry">
                    <span class="kp-file-icon">{getFileIcon(fileName)}</span>
                    <div class="kp-file-info">
                      <span class="kp-file-name">{fileName}</span>
                      <span class="kp-file-chunks">{group.chunk_count} chunks</span>
                    </div>
                    <button
                      class="kp-entry-del"
                      onclick={() => removeFile(fileName)}
                      title="Delete file"
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

          <!-- Manual entries list -->
          <div class="kp-section">
            <p class="kp-section-title">{t('bot_edit.section_manual', lang)}</p>
            <div class="kp-list">
              {#if manualEntries.length === 0}
                <div class="kp-empty">
                  <p>{t('knowledge.no_manual_entries_hint', lang)}</p>
                </div>
              {:else}
                {#each manualEntries as entry (entry.id)}
                  <div class="kp-entry">
                    <p class="kp-entry-text">{entry.content}</p>
                    <button
                      class="kp-entry-del"
                      onclick={() => removeEntry(entry.id)}
                      title="Delete"
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
              {/if}
            </div>
          </div>
        {:else}
          <p class="kp-noselect">{t('knowledge.select_bot', lang)}</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  :root {
    --kp-bg-card: #ffffff;
    --kp-border: rgba(0, 0, 0, 0.06);
    --kp-border-strong: rgba(0, 0, 0, 0.1);
    --kp-text: #1d1d1f;
    --kp-text-secondary: #6e6e73;
    --kp-text-tertiary: #86868b;
    --kp-hover: rgba(0, 0, 0, 0.03);
    --kp-selected: rgba(99, 102, 241, 0.08);
    --kp-blue: hsl(211, 100%, 50%);
    --kp-shadow-ring: rgba(0, 0, 0, 0.04);
    --kp-shadow-inset: rgba(0, 0, 0, 0.02);
    --kp-bg: #f5f5f7;
    --kp-red: #ff3b30;
  }
  :root.dark {
    --kp-bg-card: #101111;
    --kp-border: rgba(255, 255, 255, 0.06);
    --kp-border-strong: rgba(255, 255, 255, 0.1);
    --kp-text: #f9f9f9;
    --kp-text-secondary: #9c9c9d;
    --kp-text-tertiary: #6a6b6c;
    --kp-hover: rgba(255, 255, 255, 0.03);
    --kp-selected: rgba(99, 102, 241, 0.15);
    --kp-blue: hsl(202, 100%, 67%);
    --kp-shadow-ring: rgb(27, 28, 30);
    --kp-shadow-inset: rgb(7, 8, 10);
    --kp-bg: #07080a;
    --kp-red: #ff6363;
  }

  .kp-page {
    padding: 32px 48px;
    color: var(--kp-text);
  }
  .kp-header {
    margin-bottom: 28px;
  }
  .kp-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 24px;
    font-weight: 500;
    letter-spacing: 0.2px;
    margin: 0;
    color: var(--kp-text);
  }
  .kp-subtitle {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--kp-text-secondary);
    margin: 4px 0 0;
  }
  .kp-loading {
    display: flex;
    justify-content: center;
    padding: 80px 0;
  }
  .kp-layout {
    display: flex;
    gap: 32px;
  }

  /* ─── Sidebar ─── */
  .kp-sidebar {
    width: 200px;
    flex-shrink: 0;
  }
  .kp-sidebar-label {
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--kp-text-tertiary);
    margin: 0 0 12px 4px;
  }
  .kp-bot-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .kp-bot-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--kp-text-secondary);
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s ease;
    text-align: left;
  }
  .kp-bot-btn:hover {
    background: var(--kp-hover);
    color: var(--kp-text);
  }
  .kp-bot-btn.selected {
    background: var(--kp-selected);
    color: var(--kp-text);
  }
  .kp-bot-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .kp-bot-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ─── Main ─── */
  .kp-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .kp-bar {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .kp-bar-info {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    color: var(--kp-text-secondary);
    letter-spacing: 0.2px;
  }
  .kp-bar-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 86px;
    font-size: 11px;
    font-weight: 600;
    background: color-mix(in srgb, var(--kp-blue) 12%, transparent);
    color: var(--kp-blue);
  }
  .kp-bar-bot {
    font-weight: 500;
    color: var(--kp-text);
  }

  .kp-add-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }
  .kp-add-input {
    flex: 1;
  }

  /* ─── Upload ─── */
  .kp-upload-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .kp-upload-label {
    cursor: pointer;
  }
  .kp-upload-input {
    display: none;
  }
  .kp-upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 86px;
    background: transparent;
    color: var(--kp-text);
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.3px;
    transition: opacity 0.15s ease;
    box-shadow:
      color-mix(in srgb, var(--kp-text) 10%, transparent) 0px 1px 0px 0px inset,
      color-mix(in srgb, #000 3%, transparent) 0px 7px 3px;
    border: 1px solid var(--kp-border-strong);
  }
  .kp-upload-btn:hover {
    opacity: 0.7;
  }
  .kp-upload-btn.uploading {
    opacity: 0.5;
    cursor: wait;
  }
  .kp-upload-hint {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    color: var(--kp-text-tertiary);
  }
  .kp-upload-result {
    padding: 10px 14px;
    border-radius: 8px;
    background: color-mix(in srgb, #34c759 10%, transparent);
    color: #34c759;
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
  }

  /* ─── Sections ─── */
  .kp-section {
    margin-top: 16px;
  }
  .kp-section-title {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--kp-text-secondary);
    margin: 0 0 8px 4px;
  }

  /* ─── File entries ─── */
  .kp-file-entry {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--kp-border);
    transition: background 0.1s ease;
  }
  .kp-file-entry:last-child {
    border-bottom: none;
  }
  .kp-file-entry:hover {
    background: var(--kp-hover);
  }
  .kp-file-entry:hover .kp-entry-del {
    opacity: 1;
  }
  .kp-file-icon {
    font-size: 20px;
    flex-shrink: 0;
  }
  .kp-file-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .kp-file-name {
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--kp-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kp-file-chunks {
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    color: var(--kp-text-tertiary);
  }

  .kp-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--kp-border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow:
      var(--kp-shadow-ring) 0px 0px 0px 1px,
      var(--kp-shadow-inset) 0px 0px 0px 1px inset;
  }
  .kp-empty {
    padding: 32px 20px;
    text-align: center;
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    color: var(--kp-text-tertiary);
  }
  .kp-entry {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--kp-border);
    transition: background 0.1s ease;
  }
  .kp-entry:last-child {
    border-bottom: none;
  }
  .kp-entry:hover {
    background: var(--kp-hover);
  }
  .kp-entry-text {
    flex: 1;
    min-width: 0;
    font-family: 'Maple Mono', sans-serif;
    font-size: 13px;
    font-weight: 400;
    color: var(--kp-text);
    letter-spacing: 0.15px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .kp-entry-del {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--kp-text-tertiary);
    cursor: pointer;
    transition: all 0.12s ease;
    flex-shrink: 0;
    opacity: 0;
  }
  .kp-entry:hover .kp-entry-del {
    opacity: 1;
  }
  .kp-entry-del:hover {
    background: color-mix(in srgb, var(--kp-red) 10%, transparent);
    color: var(--kp-red);
  }

  .kp-noselect {
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    color: var(--kp-text-tertiary);
    padding: 40px 0;
    text-align: center;
  }

  /* ─── Textarea override ─── */
  :global(.kp-page .textarea) {
    background: var(--kp-bg) !important;
    border: 1px solid var(--kp-border) !important;
    border-radius: 8px !important;
    color: var(--kp-text) !important;
    font-family: 'Maple Mono', sans-serif !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    letter-spacing: 0.2px;
    box-shadow: none !important;
    transition: border-color 0.15s ease !important;
  }
  :global(.kp-page .textarea:focus) {
    border-color: var(--kp-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--kp-blue) 8%, transparent) !important;
  }
  :global(.kp-page .textarea::placeholder) {
    color: var(--kp-text-tertiary) !important;
  }

  @media (max-width: 768px) {
    .kp-page {
      padding: 20px 16px;
    }
    .kp-layout {
      flex-direction: column;
    }
    .kp-sidebar {
      width: 100%;
    }
    .kp-bot-list {
      flex-direction: row;
      flex-wrap: wrap;
    }
  }
</style>
