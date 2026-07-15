<!-- ThreadTree.svelte — renders a flat Thread[] as a tree of
     parent/child relationships with a file-explorer look.

     Used by BotPreviewPage and Chat.svelte to show recent chats
     for the current bot. Roots come pre-sorted DESC by
     ``last_message_at`` (most recently active thread first);
     children within each parent stay in chronological ASC order
     (older forks above newer ones — feels right for a tree where
     the parent is the "branch point").

     Visual hierarchy:
       * avatar (persona) | name + persona line | fork chip
                                          | last-active time
                                          | message count badge
       * children are visually indented with an L-shaped
         connector (vertical bar from parent + horizontal bar to
         each child). Marked via the ``.tt-row--has-children`` /
         ``.tt-row--child`` modifier classes so the CSS only draws
         lines where they make sense.

     Tailwind v4 — colors via ``bg-[var(--ray-*)]`` / ``text-[var(--ray-*)]``
     arbitrary value syntax. The two token systems (--ray-* from
     DESIGN.md and --color-surface-* from @theme) coexist by
     design — see app.css and DESIGN.md "Colors". -->
<script lang="ts">
  import { SvelteMap } from 'svelte/reactivity';

  import { type Thread, thumbUrl } from './api';
  import { t } from './i18n';
  import { formatRelativeTime } from './time';
  import { GeneratedAvatar } from './ui';

  // ── Props ──────────────────────────────────────────────────────
  const {
    botAvatarPath = null as null | string,
    botId,
    lang = 'en',
    onselectThread,
    selectedThreadId = null as null | number,
    threads = [] as Thread[],
  }: {
    /** Optional bot avatar shown when a thread has no linked
     *  persona (the thread is then a "self" chat — common in
     *  assistant-type bots). Falls back to GeneratedAvatar. */
    botAvatarPath?: null | string;
    botId: number;
    lang?: string;
    onselectThread: (botId: number, threadId: number) => void;
    selectedThreadId?: null | number;
    threads?: Thread[];
  } = $props();

  // ── Build the tree in O(n) via a Map lookup ──────────────────
  // Each node gets a ``children`` array populated from the flat
  // list. Roots are nodes whose parent_thread_id is null OR points
  // to a thread not in the passed list (orphaned parent — keep
  // visible rather than dropping data).
  interface TreeNode {
    children: TreeNode[];
    depth: number;
    thread: Thread;
  }

  function buildTree(list: Thread[]): TreeNode[] {
    const byId = new SvelteMap<number, TreeNode>();
    for (const th of list) {
      if (th.id != null) {
        byId.set(th.id, { children: [], depth: 0, thread: th });
      }
    }
    const roots: TreeNode[] = [];
    for (const node of byId.values()) {
      const parentId = node.thread.parent_thread_id;
      if (parentId != null && byId.has(parentId)) {
        byId.get(parentId)!.children.push(node);
      } else {
        roots.push(node);
      }
    }

    // Roots DESC by last activity (fall back to created_at when
    // last_message_at hasn't been populated yet — empty threads).
    // This matches the user's mental model: "the chat I was in 5
    // minutes ago goes on top, not the one I opened last week".
    const rootsActivityCmp = (a: TreeNode, b: TreeNode): number => {
      const aTime =
        Date.parse(a.thread.last_message_at ?? a.thread.created_at ?? '') || 0;
      const bTime =
        Date.parse(b.thread.last_message_at ?? b.thread.created_at ?? '') || 0;
      return bTime - aTime;
    };
    roots.sort(rootsActivityCmp);

    // Children ASC by created_at — chronological forks under the
    // parent. Oldest fork first, newest last.
    const createdAtCmp = (a: TreeNode, b: TreeNode): number => {
      const aTime = a.thread.created_at ? Date.parse(a.thread.created_at) : 0;
      const bTime = b.thread.created_at ? Date.parse(b.thread.created_at) : 0;
      return aTime - bTime;
    };
    const sortRecursive = (nodes: TreeNode[]): void => {
      nodes.sort(createdAtCmp);
      for (const n of nodes) sortRecursive(n.children);
    };
    sortRecursive(roots);

    // Propagate depth down the tree once children are assigned.
    const assignDepth = (nodes: TreeNode[], depth: number): void => {
      for (const n of nodes) {
        n.depth = depth;
        assignDepth(n.children, depth + 1);
      }
    };
    assignDepth(roots, 0);
    return roots;
  }

  const tree = $derived(buildTree(threads));

  interface FlatRow {
    depth: number;
    hasSiblingsAbove: boolean;
    isLastChild: boolean;
    node: TreeNode;
    parentName: null | string;
  }

  // Flatten the tree to a render list with depth + parent-name
  // info + sibling flags. The sibling flags feed the L-shaped
  // connector CSS — ``isLastChild`` draws the trunk only as far
  // as the last child to avoid a stray bar below the bottom fork.
  function flatten(roots: TreeNode[]): FlatRow[] {
    const out: FlatRow[] = [];
    const visit = (
      node: TreeNode,
      depth: number,
      parentName: null | string,
    ): void => {
      const thisName = node.thread.name;
      for (const child of node.children) {
        visit(child, depth + 1, thisName);
      }
      out.push({ depth, hasSiblingsAbove: false, isLastChild: false, node, parentName });
    };
    for (const r of roots) visit(r, 0, null);
    return out;
  }

  // Second pass: walk each parent's children list and stamp
  // sibling flags on them. Doing this here (vs. inside the DFS)
  // keeps ``flatten()`` above readable as a pure DFS without
  // peeking at neighbour indices.
  function attachSiblingFlags(rows: FlatRow[]): FlatRow[] {
    // SvelteMap so this collection participates in Svelte 5
    // reactivity. A plain Map would be silently inert to reads
    // from inside $derived blocks — which is fine here because
    // we only mutate once per derivation pass — but the linter
    // catches it, and future maintainers shouldn't have to wonder
    // whether the choice was deliberate.
    const parentOrder: SvelteMap<number, number[]> = new SvelteMap();
    const parentIdOf = (row: FlatRow): null | number => {
      if (row.depth === 0) return null;
      return row.node.thread.parent_thread_id ?? null;
    };
    rows.forEach((r, idx) => {
      const pid = parentIdOf(r);
      if (pid == null) return;
      const arr = parentOrder.get(pid) ?? [];
      arr.push(idx);
      parentOrder.set(pid, arr);
    });
    for (const indices of parentOrder.values()) {
      indices.forEach((rowIdx, posInParent) => {
        const r = rows[rowIdx];
        r.hasSiblingsAbove = posInParent > 0;
        r.isLastChild = posInParent === indices.length - 1;
      });
    }
    return rows;
  }

  const flat = $derived(attachSiblingFlags(flatten(tree)));

  // ── Helpers ───────────────────────────────────────────────────
  function timeAgo(dateStr: null | string): string {
    if (!dateStr) return '';
    return formatRelativeTime(dateStr, lang);
  }

  // Resolves the avatar to show in the row. Priority:
  //   1. persona_avatar_path (if a persona is linked and has one)
  //   2. botAvatarPath prop (bot's own avatar — fallback for
  //      "self" chats on assistant-type bots)
  //   3. initial-letter placeholder
  function avatarFor(thread: Thread): {
    alt: string;
    placeholder: string;
    src: null | string;
  } {
    const persona = thread.persona_name ?? '';
    if (thread.persona_avatar_path) {
      return { alt: persona, placeholder: '', src: thumbUrl(thread.persona_avatar_path, 50) };
    }
    if (botAvatarPath) {
      return { alt: thread.name, placeholder: '', src: thumbUrl(botAvatarPath, 50) };
    }
    const initial = (persona || thread.name || '?').charAt(0).toUpperCase();
    return { alt: thread.name, placeholder: initial, src: null };
  }
</script>

{#if threads.length === 0}
  <div
    class="py-10 px-4 text-center text-[13px] font-[Maple_Mono,system-ui,sans-serif] text-[var(--ray-text-tertiary)]"
  >
    {t('chat.tree.empty', lang)}
  </div>
{:else}
  <div class="tt-list flex flex-col gap-[2px] [--tt-indent:22px] [--tt-bar-x:18px]">
    {#each flat as row (row.node.thread.id)}
      {@const thread = row.node.thread}
      {@const hasChildren = row.node.children.length > 0}
      {@const av = avatarFor(thread)}
      <button
        class={[
          'tt-row group relative flex w-full items-center gap-3',
          'border border-[var(--ray-border-card)] bg-[var(--ray-surface)]',
          'rounded-lg px-3 text-left font-[Maple_Mono,system-ui,sans-serif] text-[var(--ray-text)]',
          'cursor-pointer transition-[background,border-color] duration-150 ease-out',
          'hover:bg-[color-mix(in_srgb,var(--ray-text)_5%,transparent)]',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ray-blue)]',
          hasChildren && 'tt-row--has-children',
          row.depth > 0 && 'tt-row--child',
          row.isLastChild && 'tt-row--last-child',
          selectedThreadId === thread.id &&
            'border-[color-mix(in_srgb,var(--ray-blue)_30%,transparent)] bg-[color-mix(in_srgb,var(--ray-blue)_12%,transparent)]',
        ]
          .filter(Boolean)
          .join(' ')}
        style="--tt-depth: {row.depth}; padding-left: calc(0.75rem + var(--tt-depth, 0) * var(--tt-indent)); padding-right: 0.75rem; padding-top: 0.625rem; padding-bottom: 0.625rem;"
        onclick={() => onselectThread(botId, thread.id ?? 0)}
        type="button"
      >
        <!--
          Persona / bot avatar. Falls back to a colored
          GeneratedAvatar when there's no persona image; that's a
          visual hint that this is a "self" chat.
        -->
        <div class="tt-avatar flex h-8 w-8 shrink-0 items-center justify-center">
          {#if av.src}
            <img
              src={av.src}
              alt={av.alt}
              class="tt-avatar-img h-full w-full rounded-full object-cover"
            />
          {:else if thread.persona_name}
            <GeneratedAvatar name={thread.persona_name} size={32} />
          {:else}
            <div
              class="flex h-full w-full items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--ray-text)_10%,transparent)] text-[13px] font-semibold text-[var(--ray-text-secondary)]"
            >
              {av.placeholder}
            </div>
          {/if}
        </div>

        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="truncate text-[13px] font-semibold tracking-[0.2px] text-[var(--ray-text)]">
              {thread.name}
            </span>
            {#if thread.parent_thread_id != null}
              <span
                class="inline-flex items-center gap-1 rounded-sm bg-[color-mix(in_srgb,var(--ray-blue)_14%,transparent)] px-2 py-[2px] text-[10px] font-semibold uppercase tracking-[0.3px] text-[var(--ray-blue)]"
              >
                <svg
                  width="9"
                  height="9"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                  ><circle cx="6" cy="3" r="2"></circle><circle
                    cx="6"
                    cy="21"
                    r="2"
                  ></circle><circle cx="18" cy="12" r="2"></circle><path
                    d="M6 5v14"
                  ></path><path d="M6 12c0-3.31 2.69-6 6-6h0"></path></svg
                >
                {t('chat.tree.fork_badge', lang)}
              </span>
              {#if row.parentName}
                <button
                  class="rounded-full border border-[var(--ray-border-card)] bg-[color-mix(in_srgb,var(--ray-text)_5%,transparent)] px-2 py-[2px] text-[11px] text-[var(--ray-text-secondary)] transition-colors duration-150 ease-out hover:bg-[color-mix(in_srgb,var(--ray-blue)_14%,transparent)] hover:text-[var(--ray-blue)]"
                  type="button"
                  aria-label={t('chat.tree.forked_from', lang, {
                    parent_name: row.parentName,
                  })}
                  onclick={(e: MouseEvent) => {
                    e.stopPropagation();
                    if (thread.parent_thread_id != null) {
                      onselectThread(botId, thread.parent_thread_id);
                    }
                  }}
                >
                  ↳ {t('chat.tree.forked_from', lang, { parent_name: row.parentName })}
                </button>
              {/if}
            {/if}
            {#if hasChildren}
              <span
                class="rounded-full bg-[color-mix(in_srgb,var(--ray-accent)_14%,transparent)] px-2 py-[2px] text-[10px] font-semibold text-[var(--ray-accent)]"
                title={t('chat.tree.has_forks', lang, { n: row.node.children.length })}
              >
                {t('chat.tree.has_forks', lang, { n: row.node.children.length })}
              </span>
            {/if}
          </div>
          {#if thread.summary}
            <div class="mt-[3px] truncate text-[11px] italic tracking-[0.1px] text-[var(--ray-text-secondary)]">
              {thread.summary}
            </div>
          {:else if thread.last_message_preview}
            <div class="mt-[3px] truncate text-[11px] tracking-[0.1px] text-[var(--ray-text-secondary)]">
              {thread.last_message_preview}
            </div>
          {/if}
        </div>

        <!--
          Message count badge: a small pill on the right side.
          Hidden for empty threads (message_count <= 0) to avoid
          visual noise — a freshly-created fork shouldn't draw
          attention just for being a fork.
        -->
        {#if thread.message_count > 0}
          <span
            class="ml-1 inline-flex h-[22px] min-w-[22px] shrink-0 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--ray-text)_8%,transparent)] px-2 text-[11px] font-semibold tracking-[0.2px] text-[var(--ray-text-secondary)] tabular-nums"
            aria-label={t('chat.tree.message_count_aria', lang, {
              n: thread.message_count,
            })}
          >
            {thread.message_count}
          </span>
        {/if}

        <div
          class="ml-2 min-w-[48px] shrink-0 text-right text-[11px] tracking-[0.1px] text-[var(--ray-text-tertiary)] tabular-nums"
        >
          {timeAgo(thread.last_message_at ?? thread.created_at)}
        </div>
      </button>
    {/each}
  </div>
{/if}

<style>
  /* ── L-shaped connector system ─────────────────────────────────
     The ONLY piece of CSS that can't be expressed in Tailwind
     utilities: the vertical + horizontal bars need
     ``::before``/``::after`` pseudo-elements anchored at
     specific left positions depending on whether the row is a
     last child (no bar below) or has siblings above (bar
     continues). Tailwind doesn't have arbitrary math against
     custom properties, and the per-row --tt-depth is set inline
     by the template — pseudo-element positioning is the cleanest
     path here.

     Everything else (colors, spacing, typography) is on the
     template via utility classes. This file only owns the
     connector geometry. */

  /* Vertical trunk drawn on every non-root row at the indent
     position. ``.tt-row--last-child`` shortens it (no bar below
     the last fork — same idea as the bottom of a file-explorer
     tree). */
  .tt-row--child::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: calc((var(--tt-depth, 0) - 1) * var(--tt-indent) + var(--tt-bar-x));
    width: 1px;
    background: var(--ray-border-card);
    pointer-events: none;
  }
  .tt-row--child.tt-row--last-child::before {
    bottom: 50%;
  }

  /* Horizontal connector from the trunk to this child row. */
  .tt-row--child::after {
    content: '';
    position: absolute;
    top: 50%;
    left: calc((var(--tt-depth, 0) - 1) * var(--tt-indent) + var(--tt-bar-x));
    width: calc(var(--tt-indent) - var(--tt-bar-x) + 4px);
    height: 1px;
    background: var(--ray-border-card);
    pointer-events: none;
  }

  /* Parent highlight: a row that has children gets a slightly
     warmer accent background so the eye reads "this is the
     branch point". Stays Tailwind-friendly via a custom class
     for the slight bg shift only. */
  .tt-row--has-children {
    background: color-mix(in srgb, var(--ray-accent) 4%, var(--ray-surface));
  }
  .tt-row--has-children:hover {
    background: color-mix(in srgb, var(--ray-accent) 8%, var(--ray-surface));
  }
</style>