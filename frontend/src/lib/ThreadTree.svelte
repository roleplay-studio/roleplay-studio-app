<!-- ThreadTree.svelte — renders a flat Thread[] as a tree of
     parent/child relationships, indented by depth, with a
     clickable parent chip on fork nodes. Used by BotPreviewPage
     and Chat.svelte to replace the previous flat RecentChats list. -->
<script lang="ts">
  import { SvelteMap } from 'svelte/reactivity';

  import type { Thread } from './api';

  import { t } from './i18n';
  import { formatRelativeTime } from './time';

  // ── Props ──────────────────────────────────────────────────────
  const {
    botId,
    lang = 'en',
    onselectThread,
    selectedThreadId = null as null | number,
    threads = [] as Thread[],
  }: {
    botId: number;
    lang?: string;
    onselectThread: (botId: number, threadId: number) => void;
    selectedThreadId?: null | number;
    threads?: Thread[];
  } = $props();

  // ── Build the tree in O(n) via a Map lookup ──────────────────
  // Each node gets a `children` array populated from the flat list.
  // Roots are nodes whose parent_thread_id is null OR points to
  // a thread not in the passed list (orphaned parent — defensive
  // case where the FK still points somewhere the client doesn't
  // know about).
  interface TreeNode {
    children: TreeNode[];
    depth: number;
    thread: Thread;
  }

  function buildTree(list: Thread[]): TreeNode[] {
    const byId = new SvelteMap<number, TreeNode>();
    for (const t of list) {
      if (t.id != null) {
        byId.set(t.id, { children: [], depth: 0, thread: t });
      }
    }
    const roots: TreeNode[] = [];
    for (const node of byId.values()) {
      const parentId = node.thread.parent_thread_id;
      if (parentId != null && byId.has(parentId)) {
        // Real fork — known parent exists in the list. Belongs as a
        // child. ``flatten()`` later propagates depth from the
        // parent's depth + 1.
        byId.get(parentId)!.children.push(node);
      } else {
        // No parent OR parent isn't in the list (orphaned FK — keep
        // visible rather than dropping data). Render as a root.
        roots.push(node);
      }
    }
    // Propagate depth down the tree once children are assigned.
    const assignDepth = (nodes: TreeNode[], depth: number): void => {
      for (const n of nodes) {
        n.depth = depth;
        assignDepth(n.children, depth + 1);
      }
    };
    assignDepth(roots, 0);

    // Sort children of each node by created_at ASC. Roots come
    // pre-sorted by the SQL ORDER BY (Task 3 changed list_for_bot
    // to ASC); re-sort defensively in case the caller passes an
    // unsorted list.
    const sortByCreated = (a: TreeNode, b: TreeNode): number => {
      const aTime = a.thread.created_at ? Date.parse(a.thread.created_at) : 0;
      const bTime = b.thread.created_at ? Date.parse(b.thread.created_at) : 0;
      return aTime - bTime;
    };
    const sortRecursive = (nodes: TreeNode[]): void => {
      nodes.sort(sortByCreated);
      for (const n of nodes) sortRecursive(n.children);
    };
    sortRecursive(roots);
    return roots;
  }

  const tree = $derived(buildTree(threads));

  // Flatten the tree to a render list with depth + parent-name
  // info. Simpler than nested snippets; lets the {#each} key be
  // thread.id for clean DOM diffing.
  interface FlatRow {
    depth: number;
    node: TreeNode;
    parentName: null | string;
  }
  function flatten(roots: TreeNode[]): FlatRow[] {
    const out: FlatRow[] = [];
    const visit = (node: TreeNode, depth: number, parentName: null | string): void => {
      const thisName = node.thread.name;
      out.push({ depth, node, parentName });
      for (const child of node.children) {
        visit(child, depth + 1, thisName);
      }
    };
    for (const r of roots) visit(r, 0, null);
    return out;
  }

  const flat = $derived(flatten(tree));

  // ── Helpers ───────────────────────────────────────────────────
  function timeAgo(dateStr: null | string): string {
    if (!dateStr) return '';
    return formatRelativeTime(dateStr, lang);
  }
</script>

{#if threads.length === 0}
  <div class="tt-empty">{t('chat.tree.empty', lang)}</div>
{:else}
  <div class="tt-list">
    {#each flat as row (row.node.thread.id)}
      {@const thread = row.node.thread}
      {@const hasChildren = row.node.children.length > 0}
      <button
        class="tt-row"
        class:tt-active={selectedThreadId === thread.id}
        style="--tt-depth: {row.depth};"
        onclick={() => onselectThread(botId, thread.id ?? 0)}
        type="button"
      >
        <div class="tt-avatar">
          <div class="tt-avatar-ph">
            {(thread.persona_name || '?').charAt(0).toUpperCase()}
          </div>
        </div>
        <div class="tt-info">
          <div class="tt-line-1">
            <span class="tt-name">{thread.name}</span>
            {#if thread.parent_thread_id != null}
              <span class="tt-fork-badge">{t('chat.tree.fork_badge', lang)}</span>
              {#if row.parentName}
                <button
                  class="tt-parent-chip"
                  type="button"
                  aria-label={t('chat.tree.forked_from', lang, { parent_name: row.parentName })}
                  onclick={(e: MouseEvent) => {
                    e.stopPropagation();
                    if (thread.parent_thread_id != null) {
                      onselectThread(botId, thread.parent_thread_id);
                    }
                  }}
                >
                  {t('chat.tree.forked_from', lang, { parent_name: row.parentName })}
                </button>
              {/if}
            {/if}
            {#if hasChildren}
              <span class="tt-forks-badge">
                {t('chat.tree.has_forks', lang, { n: row.node.children.length })}
              </span>
            {/if}
          </div>
          {#if thread.summary}
            <div class="tt-line-2 tt-summary">{thread.summary}</div>
          {/if}
        </div>
        <div class="tt-time">{timeAgo(thread.created_at)}</div>
      </button>
    {/each}
  </div>
{/if}

<style>
  .tt-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    /* Indent per depth level shared across the whole tree so the
       connector bar lines up regardless of row height. */
    --tt-indent: 18px;
  }
  .tt-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 10px;
    padding-left: calc(10px + var(--tt-depth, 0) * var(--tt-indent));
    /* Left border doubles as the tree trunk — drawn only on
       children (depth ≥ 1) so root threads don't get a stub bar
       sitting against the empty list margin. */
    border-left: calc(var(--tt-depth, 0) * 1px) solid transparent;
    border: 1px solid var(--ray-border-card, rgba(0, 0, 0, 0.06));
    border-radius: 8px;
    background: var(--ray-surface, transparent);
    color: var(--ray-text, inherit);
    text-align: left;
    cursor: pointer;
    transition: background 0.12s ease;
    font: inherit;
    position: relative;
  }
  /* Tiny L-shaped guide rendered before any non-root row. The
     \`└\` glyph + a horizontal bar give the tree a familiar
     file-explorer look without bringing in an icon set. */
  .tt-row:not(.tt-depth-0)::before {
    content: '';
    position: absolute;
    left: calc(var(--tt-depth, 0) * var(--tt-indent) - var(--tt-indent) + 6px);
    top: 50%;
    width: calc(var(--tt-indent) - 6px);
    height: 1px;
    background: var(--ray-border-card, rgba(0, 0, 0, 0.18));
  }
  .tt-row:hover {
    background: color-mix(in srgb, var(--ray-text, #000) 4%, transparent);
  }
  .tt-row.tt-active {
    background: color-mix(in srgb, var(--ray-blue, hsl(211, 100%, 50%)) 12%, transparent);
    border-color: color-mix(in srgb, var(--ray-blue, hsl(211, 100%, 50%)) 30%, transparent);
  }
  .tt-avatar {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
  }
  .tt-avatar-ph {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--ray-text, #000) 8%, transparent);
    font-size: 12px;
    font-weight: 500;
  }
  .tt-info {
    flex: 1;
    min-width: 0;
  }
  .tt-line-1 {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .tt-name {
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tt-fork-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--ray-blue) 15%, transparent);
    color: var(--ray-blue);
  }
  .tt-parent-chip {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--ray-text, #000) 5%, transparent);
    border: 1px solid var(--ray-border-card, rgba(0, 0, 0, 0.08));
    color: var(--ray-text-secondary, inherit);
    cursor: pointer;
    font: inherit;
  }
  .tt-parent-chip:hover {
    background: color-mix(in srgb, var(--ray-blue) 12%, transparent);
  }
  .tt-forks-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--ray-text, #000) 5%, transparent);
    color: var(--ray-text-tertiary, inherit);
  }
  .tt-line-2 {
    font-size: 11px;
    color: var(--ray-text-secondary, inherit);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-top: 2px;
  }
  .tt-time {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--ray-text-tertiary, inherit);
  }
  .tt-empty {
    padding: 32px 16px;
    text-align: center;
    color: var(--ray-text-tertiary, inherit);
    font-size: 13px;
  }
</style>
