<script lang="ts">
  import type { ThreadFileDTO } from './api';

  const {
    botType = 'rp',
    ondelet = (_id: number) => {},
    threadFiles = [],
  }: {
    botType?: string;
    ondelet?: (id: number) => void;
    threadFiles?: ThreadFileDTO[];
  } = $props();

  let expandedId = $state<null | number>(null);

  function toggleExpand(id: number) {
    expandedId = expandedId === id ? null : id;
  }

  function iconFor(type: string): string {
    if (type === 'image') return '🖼️';
    if (type === 'pdf') return '📄';
    return '📎';
  }
</script>

{#if threadFiles.length > 0 && botType !== 'rp'}
  <div class="px-6 py-2 border-b border-theme bg-theme-surface/30">
    <div class="flex flex-wrap gap-2">
      {#each threadFiles as file (file.id)}
        <div class="relative group">
          <button
            onclick={() => toggleExpand(file.id)}
            class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs
                   bg-surface-600/15 text-surface-300 hover:bg-surface-600/25
                   border border-surface-600/10 hover:border-surface-500/20
                   transition-all"
          >
            <span>{iconFor(file.file_type)}</span>
            <span class="max-w-[120px] truncate">{file.filename}</span>
          </button>

          <button
            onclick={(e) => {
              e.stopPropagation();
              ondelet(file.id);
            }}
            class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full
                   bg-rose-500/80 text-white text-[10px] flex items-center justify-center
                   opacity-0 group-hover:opacity-100 transition-opacity
                   hover:bg-rose-500"
          >
            ×
          </button>

          {#if expandedId === file.id && file.extracted_text}
            <div
              class="absolute bottom-full mb-1 left-0 z-50
                        w-72 max-h-48 overflow-y-auto p-2.5 rounded-xl
                        bg-surface-800/95 backdrop-blur-xl border border-surface-600/30
                        text-xs text-surface-200 shadow-2xl whitespace-pre-wrap"
            >
              {file.extracted_text.slice(0, 2000)}
              {#if file.extracted_text.length > 2000}
                <span class="text-surface-500">…</span>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
