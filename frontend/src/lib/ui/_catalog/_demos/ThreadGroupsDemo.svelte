<!-- ThreadGroupDemo.svelte — shows the collapsible bot-group section
     header used by RecentChats. Exposes the controlled-collapse state
     so the user can see both expanded and collapsed states in the
     same view without editing localStorage.

     Two variants:
     1. Two-bot listing with three threads in total, one bot
        expanded by default — exercises the bot metadata + chevron
        rotation, and shows the children snippet (row skeletons).
     2. Single-bot listing (collapsed-default) — exercises the
        controlled `isCollapsed` prop.

     No real RecentThread payloads — we synthesise inline so the demo
     stays self-contained (no api call).
-->
<script lang="ts">
  import ThreadGroup from '../../ThreadGroup.svelte';
  import { logOnly } from '../_mocks/callbacks';

  // Local collapse state shared between both demo sections so the
  // user can toggle them on / off freely.
  let expanded = $state(true);
  let collapsed = $state(true);

  const onToggleExpanded = logOnly('toggle-expanded');
  const onToggleCollapsed = logOnly('toggle-collapsed');
</script>

<div class="tgd-stack">
  <section class="tgd-section">
    <h3 class="tgd-h">Two-bot listing — controlled collapse</h3>
    <p class="tgd-note">
      The first group's expand-state is bound to <code>expanded</code>. The second's to
      <code>collapsed</code>. Both default-expanded buttons below drive each toggle.
    </p>
    <div class="tgd-controls">
      <button class="tgd-btn" onclick={() => (expanded = !expanded)}>
        Toggle first group ({expanded ? 'expanded' : 'collapsed'})
      </button>
      <button class="tgd-btn" onclick={() => (collapsed = !collapsed)}>
        Toggle second group ({collapsed ? 'expanded' : 'collapsed'})
      </button>
    </div>

    <ThreadGroup
      bot_avatar_path=""
      bot_categories={['Helper', 'Anime']}
      bot_name="Asha"
      isCollapsed={!expanded}
      lastActivityLabel="2 мин назад"
      onToggle={onToggleExpanded}
      threadCount={3}
    >
      <!-- Each row is a flat child node of the snippet, not its own
           inner snippet — Svelte 5 disallows single-fragment
           wrappers. -->
      <div class="tgd-row">
        <div class="tgd-row-text">
          <span class="tgd-row-name">«Дмитрий нахмурился…»</span>
          <span class="tgd-row-meta">Ками · 91 сообщ. · 5 мин назад</span>
        </div>
      </div>
      <div class="tgd-row">
        <div class="tgd-row-text">
          <span class="tgd-row-name">«У озера они остановились…»</span>
          <span class="tgd-row-meta">Ками · 12 сообщ. · 1 ч назад</span>
        </div>
      </div>
    </ThreadGroup>

    <ThreadGroup
      bot_avatar_path=""
      bot_categories={['Adventure']}
      bot_name="Misha"
      isCollapsed={!collapsed}
      lastActivityLabel="3 дн назад"
      onToggle={onToggleCollapsed}
      threadCount={1}
    >
      <div class="tgd-row">
        <div class="tgd-row-text">
          <span class="tgd-row-name">«Добро пожаловать в университет!»</span>
          <span class="tgd-row-meta">Ками · 3 сообщ. · 3 дн назад</span>
        </div>
      </div>
    </ThreadGroup>
  </section>

  <section class="tgd-section">
    <h3 class="tgd-h">Single group — without categories</h3>
    <p class="tgd-note">
      No avatar, no categories — exercises the placeholder initial
      and the no-pill fallback path.
    </p>
    <ThreadGroup
      bot_avatar_path={null}
      bot_categories={[]}
      bot_name="Без имени"
      isCollapsed={false}
      lastActivityLabel="только что"
      onToggle={logOnly('toggle-empty')}
      threadCount={1}
    >
      <div class="tgd-row">
        <div class="tgd-row-text">
          <span class="tgd-row-name">«…»</span>
          <span class="tgd-row-meta">— · 1 сообщ. · только что</span>
        </div>
      </div>
    </ThreadGroup>
  </section>
</div>

<style>
  .tgd-stack {
    display: flex;
    flex-direction: column;
    gap: 32px;
    max-width: 480px;
    font-family: 'Maple Mono', monospace;
  }
  .tgd-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .tgd-h {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ray-text-secondary);
  }
  .tgd-note {
    margin: 0 0 4px;
    font-size: 12px;
    color: var(--ray-text-tertiary);
    line-height: 1.5;
  }
  .tgd-note code {
    font-family: 'Maple Mono', monospace;
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 6%, transparent);
    padding: 1px 4px;
    border-radius: 4px;
  }
  .tgd-controls {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .tgd-btn {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-secondary);
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 5%, transparent);
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.06));
    border-radius: 6px;
    padding: 4px 10px;
    cursor: pointer;
  }
  .tgd-btn:hover {
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 10%, transparent);
  }

  /* Skeleton row used in place of a real RecentThread row — the
     demo's purpose is the group header + collapse control. */
  .tgd-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    margin: 4px 8px;
    background: var(--ray-surface, #ffffff);
    border: 1px solid var(--ray-border, rgba(0, 0, 0, 0.06));
    border-radius: 10px;
  }
  :global(.dark) .tgd-row {
    background: var(--ray-surface, #101111);
  }
  .tgd-row-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }
  .tgd-row-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--ray-text, #1d1d1f);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tgd-row-meta {
    font-size: 11px;
    color: var(--ray-text-tertiary, #86868b);
  }
</style>
