<!-- FileAttachmentsDemo.svelte — thread file chips with click-to-expand text + delete -->
<script lang="ts">
  import type { ThreadFileDTO } from '../../../api';

  import FileAttachments from '../../../FileAttachments.svelte';

  const FILES: ThreadFileDTO[] = [
    {
      created_at: '2026-05-12T10:30:00Z',
      extracted_text:
        'Aria grew up in the highlands, daughter of a healer. She learned herbcraft from her mother and swordplay from her father. At seventeen, she left to find her brother who disappeared during the war.',
      file_type: 'text',
      filename: 'character-backstory.md',
      id: 1,
      message_id: 42,
      storage_path: '/uploads/character-backstory.md',
      thread_id: 7,
    },
    {
      created_at: '2026-05-12T10:31:00Z',
      extracted_text: null,
      file_type: 'image',
      filename: 'world-map.png',
      id: 2,
      message_id: 42,
      storage_path: '/uploads/world-map.png',
      thread_id: 7,
    },
    {
      created_at: '2026-05-12T10:32:00Z',
      extracted_text:
        'Chapter 1: The Pact. The five houses of the realm signed the Pact of Ashwood in the year 312. Each house swore fealty to the Crown and bound their bloodline to defend the Border.',
      file_type: 'pdf',
      filename: 'rules.pdf',
      id: 3,
      message_id: 42,
      storage_path: '/uploads/rules.pdf',
      thread_id: 7,
    },
  ];

  let files = $state<ThreadFileDTO[]>(FILES);
  const handleDelete = (id: number) => {
    files = files.filter((f) => f.id !== id);
  };
</script>

<div class="fad-stack">
  <FileAttachments botType="assistant" threadFiles={files} ondelet={handleDelete} />
  {#if files.length === 0}
    <p class="fad-empty">All files deleted.</p>
  {/if}
</div>

<style>
  .fad-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .fad-empty {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
