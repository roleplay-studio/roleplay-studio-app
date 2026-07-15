<!-- ThreadItemsDemo.svelte — isolated ThreadItem demo.

   Exercises the enriched fields introduced in Phase 2 of the
   thread-list feature:
   - ``message_count``     — total active-chain messages per row
   - ``persona_avatar_path`` — persona avatar (or GeneratedAvatar fallback)
   - ``last_message_preview`` / ``summary`` — preview text fallback chain
   - ``persona_name``      — meta-line label

   Variants cover: with-persona, selected, without-persona, multi-message,
   empty-message, and renaming.
-->
<script lang="ts">
  import type { Thread } from '../../../api';

  import ThreadItem from '../../../ui/ThreadItem.svelte';
  import { logOnly } from '../_mocks/callbacks';

  // A few sample threads at different "ages" so the timeLabel demo is visible
  const now = new Date();
  const minsAgo = (m: number) => new Date(now.getTime() - m * 60_000).toISOString();
  const hoursAgo = (h: number) => new Date(now.getTime() - h * 3_600_000).toISOString();
  const daysAgo = (d: number) => new Date(now.getTime() - d * 86_400_000).toISOString();

  // Standard thread — name, persona, counts, preview text.
  const t1: Thread = {
    bot_id: 1,
    created_at: minsAgo(5),
    id: 101,
    last_message_at: minsAgo(3),
    // short_content preview — what we want users to see first when present.
    last_message_preview: '"Дмитрий нахмурился и сделал шаг назад, глядя на горящий порт."',
    last_message_role: 'assistant',
    message_count: 12,
    name: 'Whispers in the dark',
    parent_thread_id: null,
    persona_avatar_path: null,
    persona_id: 1,
    persona_name: 'Aria',
    summary: null,
  };
  // Thread with summary fallback (older thread, no short_content yet).
  const t2: Thread = {
    bot_id: 1,
    created_at: hoursAgo(2),
    id: 102,
    last_message_at: hoursAgo(1),
    last_message_preview: null,
    last_message_role: 'assistant',
    message_count: 4,
    name: 'The merchant encounter',
    parent_thread_id: null,
    persona_avatar_path: null,
    persona_id: 1,
    persona_name: 'Aria',
    summary: 'Met a friendly merchant on the road; traded stories over ale.',
  };
  // No persona at all — exercises the GeneratedAvatar fallback path.
  const t3: Thread = {
    bot_id: 2,
    created_at: daysAgo(1),
    id: 103,
    last_message_at: daysAgo(1),
    last_message_preview: null,
    last_message_role: 'user',
    message_count: 0,
    name: 'Code review session',
    parent_thread_id: null,
    persona_avatar_path: null,
    persona_id: null,
    persona_name: null,
    summary: null,
  };
  // Heavy-traffic thread — count badge reads as a real number.
  const t4: Thread = {
    bot_id: 1,
    created_at: hoursAgo(8),
    id: 104,
    last_message_at: minsAgo(15),
    last_message_preview: '"..." — и тут Дмитрий замолчал, ожидая ответа.',
    last_message_role: 'assistant',
    message_count: 666,
    name: 'Ками настойчиво пробирается через орду гоблинов',
    parent_thread_id: null,
    persona_avatar_path: null,
    persona_id: 1,
    persona_name: 'Ками',
    summary: null,
  };

  const onselect = logOnly<(id: number) => void>('select');
  const oncontextmenu = logOnly('contextmenu');
  const ondotsclick = logOnly('dots-click');
  const onrename = logOnly<(id: number, name: string) => void>('rename-commit');
  const oncancelrename = logOnly('rename-cancel');

  // Local state to demo the rename flow
  let renamingId = $state<null | number>(null);
  let renameDraft = $state('');

  function startRename(t: Thread) {
    renamingId = t.id;
    renameDraft = t.name;
  }
  function commitRename(id: number, name: string) {
    onrename(id, name);
    renamingId = null;
  }
  function cancelRename(id: number) {
    oncancelrename(id);
    renamingId = null;
  }
</script>

<div class="tid-stack">
  <div class="tid-row">
    <span class="tid-label">Normal — 12 сообщ., short_content preview</span>
    <div class="tid-frame">
      <ThreadItem thread={t1} timeLabel="5m" {onselect} {oncontextmenu} {ondotsclick} />
    </div>
  </div>
  <div class="tid-row">
    <span class="tid-label">Selected — summary fallback</span>
    <div class="tid-frame">
      <ThreadItem thread={t2} timeLabel="2h" selected {onselect} {oncontextmenu} {ondotsclick} />
    </div>
  </div>
  <div class="tid-row">
    <span class="tid-label">Without persona — GeneratedAvatar fallback</span>
    <div class="tid-frame">
      <ThreadItem thread={t3} timeLabel="1d" {onselect} {oncontextmenu} {ondotsclick} />
    </div>
  </div>
  <div class="tid-row">
    <span class="tid-label">Heavy traffic — 666 сообщ.</span>
    <div class="tid-frame">
      <ThreadItem thread={t4} timeLabel="8h" {onselect} {oncontextmenu} {ondotsclick} />
    </div>
  </div>
  <div class="tid-row">
    <span class="tid-label">Renaming (id 102, pre-filled)</span>
    <div class="tid-frame">
      <ThreadItem
        thread={t2}
        timeLabel="2h"
        renaming={renamingId === t2.id}
        bind:renameValue={renameDraft}
        onrename={commitRename}
        oncancelrename={cancelRename}
        ondotsclick={() => startRename(t2)}
      />
      <p class="tid-hint">
        Click the dots to start renaming (mocks ThreadDrawer's "Rename" context-menu action). Press
        Enter to commit, Escape to cancel.
      </p>
    </div>
  </div>
</div>

<style>
  .tid-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .tid-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .tid-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .tid-frame {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    padding: 8px;
    background: var(--ray-bg-card, #ffffff);
    max-width: 360px;
  }
  .tid-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 6px 4px 0;
    line-height: 1.4;
  }
</style>
