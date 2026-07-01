<!-- GlobalDropZone — full-window drag-and-drop import overlay. -->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api } from './api';
  import { currentLang, t } from './i18n';

  let isDragging = $state(false);
  let dragCounter = 0;
  let errorMsg = $state<null | string>(null);
  let lang = $state('en');
  let unsubLang: (() => void) | undefined;

  onMount(() => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    window.addEventListener('dragenter', onDragEnter);
    window.addEventListener('dragleave', onDragLeave);
    window.addEventListener('dragover', onDragOver);
    window.addEventListener('drop', onDrop);
  });

  onDestroy(() => {
    unsubLang?.();
    window.removeEventListener('dragenter', onDragEnter);
    window.removeEventListener('dragleave', onDragLeave);
    window.removeEventListener('dragover', onDragOver);
    window.removeEventListener('drop', onDrop);
  });

  function onDragEnter(e: DragEvent) {
    if (!e.dataTransfer?.types?.includes('Files')) return;
    dragCounter++;
    isDragging = true;
  }

  function onDragLeave(_e: DragEvent) {
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) isDragging = false;
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
  }

  function showError(msg: string) {
    errorMsg = msg;
    setTimeout(() => (errorMsg = null), 4000);
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    dragCounter = 0;

    const file = e.dataTransfer?.files?.[0];
    if (!file) return;

    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
    if (!['.jpeg', '.jpg', '.json', '.png', '.webp'].includes(ext)) {
      showError(t('import.unsupported_file', lang));
      return;
    }

    try {
      const { id } = await api.importBot(file);
      // Wait for the new bot to become visible through the API before
      // redirecting — without this, the destination page (e.g. bot
      // editor) can race the import write and show "bot not found"
      // because its ``getBot`` lookup happens before the row is
      // committed on the backend. Up to ~2s of polling; aborts cleanly
      // on the first successful fetch.
      const deadline = Date.now() + 2000;
      while (Date.now() < deadline) {
        try {
          await api.getBot(id);
          break;
        } catch {
          await new Promise((r) => setTimeout(r, 100));
        }
      }
      window.location.hash = `/bots/${id}/edit`;
    } catch (err) {
      showError(err instanceof Error ? err.message : t('import.failed', lang));
    }
  }
</script>

{#if isDragging}
  <div
    class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm pointer-events-none"
  >
    <div
      class="bg-theme-surface/80 backdrop-blur-xl border border-theme rounded-2xl p-12 flex flex-col items-center gap-4 shadow-2xl"
    >
      <svg
        width="64"
        height="64"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="text-theme-secondary"
      >
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <p class="text-theme text-lg font-medium">
        {t('import.drop_here', lang) || 'Drop character card or JSON to import'}
      </p>
    </div>
  </div>
{/if}

{#if errorMsg}
  <div
    class="fixed bottom-6 right-6 z-[70] bg-red-500/90 text-white px-4 py-2 rounded-lg shadow-lg max-w-sm"
  >
    {errorMsg}
  </div>
{/if}
