// Lazy-load harness for chat history.
//
// The function is intentionally framework-agnostic: the only DOM it
// touches is the `sentinel` element the caller provides, and it talks
// to the caller exclusively through a single async `loadMore`
// callback. This makes it unit-testable in jsdom (no Svelte component
// required).
//
// Behavioural contract:
//   * On every IntersectionObserver `entry.isIntersecting === true`
//     event for the sentinel, `loadMore()` is called and its return
//     value is awaited before the next call can fire.
//   * If the caller resolves with `true` ("there is more"), the
//     observer is kept and the sentinel stays watched. If it resolves
//     with `false` ("nothing left"), the observer is disconnected and
//     `disconnect()` becomes a no-op.
//   * Re-entrancy is guarded: if a previous `loadMore` is still
//     pending, additional intersection events are dropped.
//   * `disconnect()` is always safe to call — multiple times, before
//     or after the observer has been torn down.
//
// Returns a `disconnect()` function the caller should invoke from
// `$effect` cleanup so the observer is removed on unmount.

export interface AttachOptions {
  /** The scrollable ancestor. `null` = the viewport. */
  root?: Element | null;
  /** Grow the root's intersection box so the load triggers slightly
   *  before the sentinel actually enters the viewport. 200px is the
   *  sweet spot — instant on desktop, enough lead on mobile. */
  rootMargin?: string;
  /** Picked up by `IntersectionObserver` unchanged. */
  threshold?: number | number[];
}
/** `true` = more available, `false` = end of list, `undefined` = unknown.
 *  Treating `undefined` as "keep watching" preserves backwards
 *  compatibility for callers that just want to trigger a fetch and
 *  let pagination short-circuit itself when the server returns a
 *  short page. */

export type Disconnect = () => void;

export type LoadMore = () => Promise<LoadResult>;

export type LoadResult = boolean | undefined;

export function attachInfiniteScroll(
  sentinel: Element,
  loadMore: LoadMore,
  options: AttachOptions = {},
): Disconnect {
  const { root = null, rootMargin = '200px 0px', threshold = 0 } = options;

  let inFlight = false;
  let stopped = false;
  let observer: IntersectionObserver | null = null;

  const onIntersect: IntersectionObserverCallback = async (entries) => {
    if (stopped || inFlight) return;
    if (!entries.some((e) => e.isIntersecting)) return;

    inFlight = true;
    try {
      const result = await loadMore();
      if (stopped) return;
      if (result === false) {
        stopped = true;
        observer?.disconnect();
        observer = null;
      }
    } finally {
      inFlight = false;
    }
  };

  observer = new IntersectionObserver(onIntersect, {
    root: root as Element | null,
    rootMargin,
    threshold,
  });
  observer.observe(sentinel);

  const disconnect: Disconnect = () => {
    stopped = true;
    observer?.disconnect();
    observer = null;
  };
  return disconnect;
}
