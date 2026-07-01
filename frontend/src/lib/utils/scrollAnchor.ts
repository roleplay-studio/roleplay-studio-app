// Scroll-anchoring helpers for chat history.
//
// The motivating problem: when new (older) messages are prepended to
// the top of a chat list, the user's visible viewport would jump
// because the content beneath their cursor moved down by however
// many pixels the new messages added. The naive "measure
// scrollHeight before/after, then add the delta to scrollTop" fix is
// unreliable when the inserted content uses `content-visibility:
// auto` + `contain-intrinsic-size` — at the time we measure the
// new height, the browser has not yet resolved the placeholder
// sizes into real heights, so the delta is *underestimated* and
// the view still jumps by the missing pixels.
//
// The robust approach is to anchor on a *specific message*: capture
// which message is at the top of the visible region before the
// prepend, then after the prepend, set `scrollTop` so that exact
// same message lands at the same offset within the scroll
// container. Whatever happens to the heights of the new bubbles
// (placeholder → real, image loads, font swap, etc.), the anchor
// message stays put.
//
// The selector is configurable so callers can use whatever DOM
// attribute they put on their message wrapper.

export interface AnchorSnapshot {
  /** Id of the message at the top of the visible viewport, or null
   *  if none of the candidate messages is currently visible. */
  readonly anchorId: null | number | string;
  /** Pixel offset of the anchor's top edge from the top of the
   *  scroll container. Positive when the anchor is below the
   *  container's top edge. */
  readonly anchorOffset: null | number;
}

/**
 * Walk the children of `scrollEl` that carry a `data-msg-id`
 * attribute and return the id + offset of the first one whose top
 * edge is at or below the top of the scroll container's visible
 * area. If no candidate is visible (e.g. the user is below the
 * last message), returns `{anchorId: null}`.
 *
 * "At or below" matters: if the first message's top edge is
 * exactly at the top of the container, we want to anchor on *it*,
 * not on whatever the second message is. That's the common case
 * after a load-more, where the freshly-prepended messages are
 * above the viewport and the previously-first visible message is
 * now N pixels down.
 *
 * Note: the elements we measure are wrappers around each
 * MessageBubble. In Chat.svelte these wrappers use
 * `display: contents` so they don't generate a layout box of
 * their own — which means `wrapper.getBoundingClientRect()`
 * returns `{top: 0, height: 0}` and is useless for anchoring.
 * We measure the wrapper's *first* layout-producing descendant
 * (typically the .mb-row inside MessageBubble) and use *its*
 * geometry. The `data-msg-id` lives on the wrapper so the
 * caller can still identify the message uniquely.
 */
export function captureScrollAnchor(
  scrollEl: HTMLElement | undefined,
  attributeName = 'data-msg-id',
): AnchorSnapshot {
  if (!scrollEl) return { anchorId: null, anchorOffset: null };
  const containerRect = scrollEl.getBoundingClientRect();
  const containerTop = containerRect.top;
  const candidates = scrollEl.querySelectorAll<HTMLElement>(`[${attributeName}]`);
  for (const wrapper of candidates) {
    // The first *layout-producing* descendant (i.e. anything that
    // isn't `display: contents` or `display: none`). We walk down
    // until we find a node with a non-zero box.
    const target = firstLayoutDescendant(wrapper) ?? wrapper;
    const top = target.getBoundingClientRect().top;
    if (top >= containerTop - 1 /* tolerance for sub-pixel rounding */) {
      return {
        anchorId: wrapper.getAttribute(attributeName),
        anchorOffset: top - containerTop,
      };
    }
  }
  return { anchorId: null, anchorOffset: null };
}

/**
 * After a prepend, set `scrollTop` so the message identified by
 * `snapshot.anchorId` sits at the same visible offset it had at
 * capture time. If the anchor is no longer in the DOM (e.g. it
 * was the first message and got scrolled off the top during the
 * prepend animation), this is a no-op — the caller can then fall
 * back to other scroll-positioning strategies.
 *
 * Should be called *after* the browser has done at least one
 * layout pass on the newly-inserted content. A `requestAnimationFrame`
 * inside a `requestAnimationFrame` is the safest pattern when
 * `content-visibility: auto` is in play, because the first rAF
 * fires *before* the browser has resolved the placeholder sizes
 * for the freshly-inserted bubbles, and the second rAF fires
 * after.
 */
export function restoreScrollAnchor(
  scrollEl: HTMLElement | undefined,
  snapshot: AnchorSnapshot,
  attributeName = 'data-msg-id',
): void {
  if (!scrollEl) return;
  if (snapshot.anchorId == null || snapshot.anchorOffset == null) return;
  const anchorEl = scrollEl.querySelector<HTMLElement>(
    `[${attributeName}="${CSS.escape(String(snapshot.anchorId))}"]`,
  );
  if (!anchorEl) return;
  const target = firstLayoutDescendant(anchorEl) ?? anchorEl;
  const containerRect = scrollEl.getBoundingClientRect();
  const newOffset = target.getBoundingClientRect().top - containerRect.top;
  scrollEl.scrollTop += newOffset - snapshot.anchorOffset;
}

/**
 * Find the first descendant of `el` that actually generates a
 * layout box. This is needed because the chat message wrapper has
 * `display: contents` and so its `getBoundingClientRect()` is
 * always `{top: 0, height: 0}` — we have to drill into the
 * MessageBubble to get a usable position.
 */
function firstLayoutDescendant(el: HTMLElement): HTMLElement | null {
  for (const child of Array.from(el.children)) {
    const node = child as HTMLElement;
    const display = getComputedStyle(node).display;
    if (display !== 'contents' && display !== 'none') {
      return node;
    }
    // contents descendants are still wrappers themselves; recurse.
    const deeper = firstLayoutDescendant(node);
    if (deeper) return deeper;
  }
  return null;
}
