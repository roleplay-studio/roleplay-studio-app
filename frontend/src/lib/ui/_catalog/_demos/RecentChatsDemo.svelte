<!-- RecentChatsDemo.svelte — loading / empty / list with mock threads -->
<script lang="ts">
  import RecentChats from '../../../RecentChats.svelte';
  import { logOnly } from '../_mocks/callbacks';
  import { mockRecentThreads } from '../_mocks/threadFixtures';

  const ondeleteThread = logOnly<(id: number) => void>('delete-thread');
  const onselectThread = logOnly<(botId: number, threadId: number) => void>('select-thread');

  const threads = mockRecentThreads(4);
</script>

<div class="rcd-stack">
  <div class="rcd-row">
    <span class="rcd-label">Loading</span>
    <div class="rcd-frame">
      <RecentChats loading threads={[]} />
    </div>
  </div>
  <div class="rcd-row">
    <span class="rcd-label">Empty</span>
    <div class="rcd-frame">
      <RecentChats threads={[]} />
    </div>
  </div>
  <div class="rcd-row">
    <span class="rcd-label">List (4 mock threads)</span>
    <div class="rcd-frame">
      <RecentChats {threads} {ondeleteThread} {onselectThread} />
    </div>
  </div>
</div>

<style>
  .rcd-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .rcd-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .rcd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .rcd-frame {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    padding: 12px 14px;
    background: var(--ray-bg-card, #ffffff);
  }
</style>
