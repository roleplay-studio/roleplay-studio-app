import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { attachInfiniteScroll, type Disconnect } from '../utils/infiniteScrollSentinel';

/**
 * A controllable IntersectionObserver substitute. Tests can drive it
 * with `trigger(entries)` to simulate viewport crossings.
 */
class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];
  callback: IntersectionObserverCallback;
  disconnected = false;

  observed: Element[] = [];
  options: IntersectionObserverInit | undefined;
  unobserveCalls: Element[] = [];
  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
    FakeIntersectionObserver.instances.push(this);
  }
  static last() {
    const i = FakeIntersectionObserver.instances.length;
    return FakeIntersectionObserver.instances[i - 1];
  }

  static reset() {
    FakeIntersectionObserver.instances = [];
  }
  disconnect() {
    this.disconnected = true;
  }
  observe(el: Element) {
    this.observed.push(el);
  }
  trigger(entries: Partial<IntersectionObserverEntry>[]) {
    const full = entries.map(
      (e) =>
        ({
          isIntersecting: false,
          target: this.observed[0] ?? null,
          ...e,
        }) as IntersectionObserverEntry,
    );
    void this.callback(full, this as unknown as IntersectionObserver);
  }
  unobserve(el: Element) {
    this.unobserveCalls.push(el);
  }
}

beforeEach(() => {
  FakeIntersectionObserver.reset();
  // jsdom doesn't ship an IntersectionObserver implementation, so we
  // install our fake as the global. The cast is intentional: our fake
  // is a class with extra statics; structurally it's compatible with
  // the constructor signature IntersectionObserver uses.
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver =
    FakeIntersectionObserver;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('attachInfiniteScroll', () => {
  it('creates an observer that watches the sentinel', () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);
    const disconnect = attachInfiniteScroll(sentinel, loadMore);
    expect(FakeIntersectionObserver.last().observed).toEqual([sentinel]);
    disconnect();
  });

  it('calls loadMore when the sentinel becomes visible', async () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);
    attachInfiniteScroll(sentinel, loadMore);

    FakeIntersectionObserver.last().trigger([{ isIntersecting: true }]);

    // The handler is async; let the microtask queue drain.
    await Promise.resolve();
    await Promise.resolve();

    expect(loadMore).toHaveBeenCalledTimes(1);
  });

  it('does not call loadMore when the entry is not intersecting', async () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);
    attachInfiniteScroll(sentinel, loadMore);

    FakeIntersectionObserver.last().trigger([{ isIntersecting: false }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(loadMore).not.toHaveBeenCalled();
  });

  it('stops watching after loadMore resolves with false', async () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(false);
    attachInfiniteScroll(sentinel, loadMore);

    const obs = FakeIntersectionObserver.last();
    obs.trigger([{ isIntersecting: true }]);

    // Drain microtasks: trigger → handler start → await loadMore → set
    // inFlight false → disconnect.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(obs.disconnected).toBe(true);
  });

  it('keeps watching when loadMore resolves with true (more available)', async () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);
    attachInfiniteScroll(sentinel, loadMore);

    const obs = FakeIntersectionObserver.last();
    obs.trigger([{ isIntersecting: true }]);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(obs.disconnected).toBe(false);
    // A second intersection should still trigger a second load.
    obs.trigger([{ isIntersecting: true }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(loadMore).toHaveBeenCalledTimes(2);
  });

  it('keeps watching when loadMore resolves with undefined', async () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(undefined);
    attachInfiniteScroll(sentinel, loadMore);

    const obs = FakeIntersectionObserver.last();
    obs.trigger([{ isIntersecting: true }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(obs.disconnected).toBe(false);
  });

  it('drops re-entrant intersection events while a load is in flight', async () => {
    const sentinel = document.createElement('div');
    let resolveLoad: (v: boolean) => void = () => {};
    const loadMore = vi.fn(
      () =>
        new Promise<boolean>((res) => {
          resolveLoad = res;
        }),
    );
    attachInfiniteScroll(sentinel, loadMore);

    const obs = FakeIntersectionObserver.last();
    obs.trigger([{ isIntersecting: true }]); // fires load #1
    await Promise.resolve(); // let handler reach the await
    obs.trigger([{ isIntersecting: true }]); // ignored — in-flight
    obs.trigger([{ isIntersecting: true }]); // ignored — in-flight
    await Promise.resolve();
    await Promise.resolve();

    expect(loadMore).toHaveBeenCalledTimes(1);

    // Finish the first load; the next intersection should now fire.
    resolveLoad(true);
    await Promise.resolve();
    await Promise.resolve();

    obs.trigger([{ isIntersecting: true }]);
    await Promise.resolve();
    await Promise.resolve();

    expect(loadMore).toHaveBeenCalledTimes(2);
  });

  it('disconnect() is idempotent', () => {
    const sentinel = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);
    const disconnect: Disconnect = attachInfiniteScroll(sentinel, loadMore);
    const obs = FakeIntersectionObserver.last();

    disconnect();
    disconnect(); // must not throw, must not re-disconnect a torn-down observer
    expect(obs.disconnected).toBe(true);
  });

  it('forwards options (root, rootMargin, threshold) to the observer', () => {
    const sentinel = document.createElement('div');
    const root = document.createElement('div');
    const loadMore = vi.fn().mockResolvedValue(true);

    attachInfiniteScroll(sentinel, loadMore, {
      root,
      rootMargin: '42px',
      threshold: [0, 1],
    });

    const obs = FakeIntersectionObserver.last();
    expect(obs.options).toEqual({
      root,
      rootMargin: '42px',
      threshold: [0, 1],
    });
  });
});
