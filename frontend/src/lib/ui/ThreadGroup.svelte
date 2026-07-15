<!-- ThreadGroup — collapsible section header for the cross-bot recent
     chats listing. Renders bot info (avatar + name + categories),
     thread count, last-activity timestamp, and a chevron that rotates
     180° when collapsed. The actual thread rows are passed in via
     a ``children`` snippet so callers stay in charge of row
     rendering.

     Designed to be sticky at the top of the scroll container so the
     user always knows which bot they're looking at as they scroll
     long lists. State (collapsed / expanded) is owned by the parent
     and persisted separately (RecentChats uses localStorage).

     Visual treatment: glass blur on the sticky header keeps the
     sections legible when scrolling over the row below.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';

  const {
    bot_avatar_path,
    bot_categories = [],
    bot_name,
    children,
    isCollapsed,
    lastActivityLabel,
    onToggle,
    threadCount,
  }: {
    bot_avatar_path: null | string;
    bot_categories?: string[];
    bot_name: string;
    children?: Snippet;
    isCollapsed: boolean;
    lastActivityLabel: string;
    onToggle: () => void;
    threadCount: number;
  } = $props();
</script>

<header
  class="tg"
  class:tg-collapsed={isCollapsed}
  role="region"
  aria-label={bot_name}
>
  <button
    type="button"
    class="tg-toggle"
    aria-expanded={!isCollapsed}
    onclick={onToggle}
  >
    <!-- Bot avatar: prefer the uploaded one, fall back to
         GeneratedAvatar block (matches RecentChats' prior visual
         treatment, so the row stays familiar). -->
    {#if bot_avatar_path}
      <img src={bot_avatar_path} alt="" class="tg-avatar tg-avatar-img" />
    {:else}
      <div class="tg-avatar tg-avatar-placeholder">{bot_name.charAt(0).toUpperCase()}</div>
    {/if}

    <div class="tg-info">
      <div class="tg-name-row">
        <span class="tg-name">{bot_name}</span>
        {#if bot_categories.length > 0}
          <span class="tg-cat">{bot_categories[0]}</span>
        {/if}
        <span class="tg-count">{threadCount}</span>
      </div>
      <div class="tg-meta">
        <span class="tg-activity">{lastActivityLabel}</span>
      </div>
    </div>

    <!-- Chevron rotates 180° when collapsed; transform-only
         animation so we don't repaint the avatar/text on toggle. -->
    <svg
      class="tg-chevron"
      class:tg-chevron-collapsed={isCollapsed}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if !isCollapsed && children}
    <div class="tg-body">
      {@render children()}
    </div>
  {/if}
</header>

<style>
  .tg {
    /* Sticky so the group header stays visible while the user
       scrolls through long thread lists. ``backdrop-filter: blur``
       gives the glass effect on the solid ``--ray-surface``
       background — fully opaque to prevent rows from leaking
       through the header strip during scroll.

       ``isolation: isolate`` + ``will-change: transform`` create
       a new stacking context that forces the browser to composite
       the header's pixels BEFORE the rows behind it, eliminating
       any ghost-text bleed. Without this, Safari/Firefox show
       row text faintly visible through the 100% opaque surface
       due to how they handle the sticky + filter combination. */
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--ray-surface, #101111);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-bottom: 3px solid var(--ray-border-card, rgba(255, 255, 255, 0.06));
    isolation: isolate;
    will-change: transform;
    margin-bottom: 5px;
    border-radius: 10px;
    overflow: hidden;
  }
  /* Dark-mode overrides — set the surface to the dark ``--ray-*``
     variables which are globally defined in :root.dark. Earlier
     this reused ``var(--tg-*, #101111)`` but ``--tg-*`` are NOT
     defined globally, so every rule landed on its light-mode
     fallback (white surface, near-black text) and rendered the
     group header with black text on a black background.
     Switching the source of truth to the Raycast palette gives us
     proper dark-mode rendering. */
  :global(.dark) .tg {
    background: var(--ray-surface, #101111);
  }
  :global(.dark) .tg-body {
    background: var(--ray-surface, #101111);
  }
  :global(.dark) .tg-name {
    color: var(--ray-text, #f9f9f9);
  }
  :global(.dark) .tg-cat {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 5%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }
  :global(.dark) .tg-count {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 6%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }
  :global(.dark) .tg-activity {
    color: var(--ray-text-tertiary, #6a6b6c);
  }
  :global(.dark) .tg-toggle:hover {
    background: var(--ray-border-card, rgba(255, 255, 255, 0.06));
  }
  :global(.dark) .tg-toggle:focus-visible {
    background: var(--ray-border-card, rgba(255, 255, 255, 0.06));
  }
  :global(.dark) .tg-avatar-placeholder {
    background: color-mix(in srgb, var(--ray-text, #f9f9f9) 6%, transparent);
    color: var(--ray-text-secondary, #9c9c9d);
  }

  .tg-toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 12px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: inherit;
    font: inherit;
    text-align: left;
    transition: background 0.12s ease;
  }
  .tg-toggle:hover {
    background: var(--ray-border-card, rgba(0, 0, 0, 0.06));
  }
  .tg-toggle:focus-visible {
    outline: none;
    background: var(--ray-border-card, rgba(0, 0, 0, 0.06));
    box-shadow: inset 0 0 0 2px color-mix(in srgb, hsl(202, 100%, 67%) 30%, transparent);
  }

  .tg-avatar {
    width: 36px;
    height: 36px;
    /* ``aspect-ratio: 1`` + ``flex-shrink: 0`` lock the box to a
       square regardless of the uploaded image's natural aspect
       ratio. Without ``aspect-ratio`` the img would scale to
       100% width and stretch its intrinsic height to whatever
       the parent container allows — observed at ~908×1365px on a
       /#/chat recent-chats listing where the parent ``tg-toggle``
       was a flex row stretching to fit the page. ``object-fit:
       cover`` then crops without leaving a stretched image.

       NOTE: ``.tg-avatar`` is applied both to the wrapping shape
       AND to the ``<img>`` (we use ``<img class="tg-avatar tg-avatar-img">``
       rather than wrapping in an extra div). The next rule
       ``.tg-avatar-img`` overrides ``width: 100%`` so the square
       36×36 box defined here doesn't shrink — instead the img
       fills the box's 100%. ``aspect-ratio`` here keeps the box
       square even when the image has no intrinsic dimension. */
    aspect-ratio: 1 / 1;
    flex-shrink: 0;
    border-radius: 8px;
    overflow: hidden;
    background: var(--ray-surface, #101111);
  }
  .tg-avatar-img {
    /* The image is itself a ``.tg-avatar`` square — width/height
       inherited from that rule. We ``object-fit: cover`` to crop.
       ``width/height: 100%`` here would override the 36×36 box
       and stretch the image back to fill its parent. Earlier this
       caused 908×1365 images in the recent-chats list. */
    object-fit: cover;
  }
  .tg-avatar-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Maple Mono', monospace;
    font-size: 16px;
    font-weight: 600;
    color: var(--ray-text-secondary, #6e6e73);
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 6%, transparent);
  }

  .tg-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .tg-name-row {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  .tg-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--ray-text, #1d1d1f);
    letter-spacing: 0.2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 0 1 auto;
    min-width: 0;
  }
  .tg-cat {
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    padding: 1px 7px;
    border-radius: 86px;
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 5%, transparent);
    color: var(--ray-text-secondary, #6e6e73);
    letter-spacing: 0.3px;
    flex-shrink: 0;
  }
  /* Thread count — small pill, monochrome. Mirrors the recent-row
     count badge styling in RecentChats so the eye tracks them
     as the same UI primitive. */
  .tg-count {
    flex-shrink: 0;
    font-family: 'Maple Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    color: var(--ray-text-secondary, #6e6e73);
    background: color-mix(in srgb, var(--ray-text, #1d1d1f) 6%, transparent);
    padding: 1px 6px;
    border-radius: 86px;
    font-feature-settings: 'tnum' 1;
    letter-spacing: 0.2px;
    margin-left: auto;
    position: relative;
    top: 10px;
  }

  .tg-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--ray-text-tertiary, #86868b);
  }
  .tg-activity {
    letter-spacing: 0.2px;
  }

  .tg-chevron {
    color: var(--tg-text-tertiary, #86868b);
    flex-shrink: 0;
    transform: rotate(0deg);
    transition: transform 0.15s ease, color 0.12s ease;
  }
  .tg-chevron-collapsed {
    transform: rotate(-90deg);
  }
  .tg:hover .tg-chevron {
    color: var(--tg-text-secondary, #6e6e73);
  }

  /* Body section — relative+lower z-index so the sticky header
     floats above the rows; each row gets a subtle top padding so
     the sticky header doesn't visually clip the first row.

     Background reads from ``--ray-surface`` (dark by default)
     so dark mode renders correctly. Earlier this used
     ``var(--tg-bg, #ffffff)`` which had no global definition
     and rendered white body even in dark mode. */
  .tg-body {
    position: relative;
    z-index: 1;
    padding-top: 2px;
    background: var(--ray-surface, #101111);
  }
</style>
