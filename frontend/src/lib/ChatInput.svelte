<script lang="ts">
  import { api, type BotType, type ThreadFileDTO } from './api';
  import { t } from './i18n';

  const {
    botId = 0,
    botType = 'rp' as BotType,
    lang = 'en',
    onsend,
    onstop,
    streaming = false,
    threadId = 0,
  }: {
    botId?: number;
    botType?: BotType;
    lang?: string;
    onsend?: (text: string, fileIds: number[]) => void;
    onstop?: () => void;
    streaming?: boolean;
    threadId?: number;
  } = $props();

  let inputText = $state('');
  let textareaEl: HTMLTextAreaElement | undefined = $state();
  let hiddenFileInput: HTMLInputElement | undefined = $state();
  let uploading = $state(false);
  let uploadError = $state('');
  let pendingFiles: ThreadFileDTO[] = $state([]);
  let isDragOver = $state(false);

  function handleSubmit(e: Event) {
    e.preventDefault();
    if (streaming) return;
    const text = inputText.trim() || '*continue*';
    const fileIds = pendingFiles.map((f) => f.id);
    onsend?.(text, fileIds);
    inputText = '';
    pendingFiles = [];
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  function wrapBold() {
    if (!textareaEl) return;
    const ta = textareaEl;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const val = ta.value;

    if (start !== end) {
      const selected = val.slice(start, end);
      const before = val.slice(0, start);
      const after = val.slice(end);
      inputText = `${before}*${selected}*${after}`;
      requestAnimationFrame(() => {
        ta.focus();
        ta.setSelectionRange(start + 1, end + 1);
      });
    } else {
      const before = val.slice(0, start);
      const after = val.slice(start);
      inputText = `${before}**${after}`;
      requestAnimationFrame(() => {
        ta.focus();
        ta.setSelectionRange(start + 1, start + 1);
      });
    }
  }

  function triggerUpload() {
    uploadError = '';
    hiddenFileInput?.click();
  }

  async function uploadFiles(files: File[] | FileList) {
    for (const file of files) {
      uploading = true;
      uploadError = '';
      try {
        const result = await api.uploadFile(threadId, botId, file);
        pendingFiles = [...pendingFiles, result];
      } catch (err: unknown) {
        const e = err as { detail?: string; message?: string };
        uploadError = e?.detail || e?.message || t('chat.upload_failed', lang);
        break;
      } finally {
        uploading = false;
      }
    }
    if (hiddenFileInput) hiddenFileInput.value = '';
  }

  async function handleFileSelected(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      await uploadFiles(target.files);
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    if (botType === 'rp' || streaming) return;
    isDragOver = true;
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragOver = false;
    if (botType === 'rp' || streaming) return;
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      uploadFiles(e.dataTransfer.files);
    }
  }

  function removePendingFile(id: number) {
    pendingFiles = pendingFiles.filter((f) => f.id !== id);
  }

  function iconFor(type: string): string {
    if (type === 'image') return '🖼️';
    if (type === 'pdf') return '📄';
    return '📎';
  }
</script>

<div
  class="ci-wrap"
  class:ci-dragging={isDragOver}
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
>
  {#if isDragOver}
    <div class="ci-drop-overlay">
      <span>{t('chat.drop_files', lang)}</span>
    </div>
  {/if}

  {#if uploadError}
    <div class="ci-error">{uploadError}</div>
  {/if}

  <!-- Pending files chips -->
  {#if pendingFiles.length > 0}
    <div class="ci-files">
      {#each pendingFiles as file (file.filename)}
        <span class="ci-file-chip">
          <span>{iconFor(file.file_type)}</span>
          <span class="ci-file-name">{file.filename}</span>
          <button onclick={() => removePendingFile(file.id)} class="ci-file-remove">×</button>
        </span>
      {/each}
    </div>
  {/if}

  <form onsubmit={handleSubmit} class="ci-form">
    <!-- Upload button -->
    {#if botType !== 'rp'}
      <input
        type="file"
        accept=".txt,.md,.pdf,.png,.jpg,.jpeg,.gif,.webp"
        bind:this={hiddenFileInput}
        class="hidden"
        multiple
        onchange={handleFileSelected}
      />
      <button
        type="button"
        class="ci-tool-btn"
        onclick={triggerUpload}
        disabled={streaming || uploading}
        title={t('chat.attach_file', lang)}
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
          ><path
            d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"
          ></path></svg
        >
      </button>
    {/if}

    <!-- Bold action -->
    {#if botType === 'rp'}
      <button
        type="button"
        class="ci-tool-btn"
        onclick={wrapBold}
        disabled={streaming}
        title={t('chat.wrap_bold', lang)}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path d="M12 6v12" /><path d="M17.196 9 6.804 15" /><path d="m6.804 9 10.392 6" /></svg
        >
      </button>
    {/if}

    <!-- Textarea -->
    <div class="ci-input-wrap top-1">
      <textarea
        bind:this={textareaEl}
        bind:value={inputText}
        rows="1"
        placeholder={t('chat.type_message', lang)}
        disabled={streaming}
        class="ci-textarea"
        onkeydown={handleKeydown}
      ></textarea>
    </div>

    <!-- Send / Stop button -->
    {#if streaming}
      <button
        type="button"
        class="ci-send-btn ci-stop-btn"
        onclick={onstop}
        title={t('chat.stop', lang)}
        aria-label={t('chat.stop', lang)}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
          <rect x="2" y="2" width="10" height="10" rx="2" />
        </svg>
      </button>
    {:else}
      <button
        type="submit"
        class="ci-send-btn"
        class:ci-send-continue={!inputText.trim()}
        title={inputText.trim() ? t('chat.send', lang) : t('chat.continue', lang)}
        aria-label={inputText.trim() ? t('chat.send', lang) : t('chat.continue', lang)}
      >
        {#if inputText.trim()}
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"
            ></polygon></svg
          >
        {:else}
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg
          >
        {/if}
      </button>
    {/if}
  </form>
</div>

<style>
  :root {
    --ci-bg: #ffffff;
    --ci-border: rgba(0, 0, 0, 0.06);
    --ci-text: #1d1d1f;
    --ci-text-secondary: #6e6e73;
    --ci-text-tertiary: #86868b;
    --ci-hover: rgba(0, 0, 0, 0.04);
    --ci-blue: hsl(211, 100%, 50%);
  }
  :root.dark {
    --ci-bg: #101111;
    --ci-border: rgba(255, 255, 255, 0.06);
    --ci-text: #f9f9f9;
    --ci-text-secondary: #9c9c9d;
    --ci-text-tertiary: #6a6b6c;
    --ci-hover: rgba(255, 255, 255, 0.04);
    --ci-blue: hsl(202, 100%, 67%);
  }

  .ci-wrap {
    border-top: 1px solid var(--ci-border);
    background: var(--ci-bg);
    flex-shrink: 0;
    position: relative;
  }
  .ci-wrap.ci-dragging {
    box-shadow: inset 0 0 0 2px var(--ci-blue);
  }
  .ci-drop-overlay {
    position: absolute;
    inset: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--ci-blue) 8%, transparent);
    backdrop-filter: blur(4px);
    pointer-events: none;
    font-family: 'Maple Mono', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--ci-blue);
  }
  .ci-error {
    font-family: 'Maple Mono', sans-serif;
    font-size: 12px;
    color: #ff6363;
    padding: 8px 16px 0;
  }
  .ci-files {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 16px 0;
  }
  .ci-file-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: 6px;
    font-family: 'Maple Mono', sans-serif;
    font-size: 11px;
    font-weight: 500;
    background: color-mix(in srgb, var(--ci-blue) 10%, transparent);
    color: var(--ci-blue);
    border: 1px solid color-mix(in srgb, var(--ci-blue) 15%, transparent);
  }
  .ci-file-name {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ci-file-remove {
    background: none;
    border: none;
    cursor: pointer;
    color: inherit;
    opacity: 0.6;
    font-size: 14px;
    padding: 0 2px;
  }
  .ci-file-remove:hover {
    opacity: 1;
  }

  .ci-form {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
  }
  .ci-tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ci-text-secondary);
    cursor: pointer;
    transition: all 0.12s ease;
    flex-shrink: 0;
  }
  .ci-tool-btn:hover {
    background: var(--ci-hover);
    color: var(--ci-text);
  }
  .ci-tool-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
  .ci-input-wrap {
    flex: 1;
    position: relative;
  }
  .ci-textarea {
    width: 100%;
    resize: none;
    background: var(--ci-bg);
    border: 1px solid var(--ci-border);
    border-radius: 10px;
    color: var(--ci-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 14px;
    padding: 9px 14px;
    letter-spacing: 0.15px;
    line-height: 1.5;
    outline: none;
    transition: border-color 0.15s ease;
    min-height: 40px;
    max-height: 120px;
    box-sizing: border-box;
  }
  .ci-textarea:focus {
    border-color: var(--ci-blue);
  }
  .ci-textarea::placeholder {
    color: var(--ci-text-tertiary);
  }
  .ci-textarea:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .ci-send-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: none;
    border-radius: 10px;
    background: var(--ci-text);
    color: var(--ci-bg);
    cursor: pointer;
    transition: opacity 0.12s ease;
    flex-shrink: 0;
  }
  .ci-send-btn:hover {
    opacity: 0.8;
  }
  .ci-send-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
  .ci-send-continue {
    background: var(--ci-blue) !important;
    color: #fff !important;
  }
  .ci-send-continue:hover {
    opacity: 0.85 !important;
  }

  /* Stop button variant — danger colour, square icon, no blue gradient */
  .ci-stop-btn {
    background: var(--ray-accent-red, #ed5f74) !important;
    color: #fff !important;
    border-color: transparent !important;
  }
  .ci-stop-btn:hover {
    opacity: 0.85 !important;
  }
</style>
