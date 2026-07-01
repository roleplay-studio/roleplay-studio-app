// _mocks/callbacks.ts — no-op and logging callbacks for catalog demos.
// No-op keeps the demo from accidentally mutating app state, logging
// helps verify a click actually fired when reviewing the /ui-kit page.

export const noop = (): void => {};

export const noopAsync = async (): Promise<void> => {};

/**
 * Wraps a callback to also console.log its args. Useful for verifying
 * on the /ui-kit page that a click actually triggered the right handler.
 * Type-erased to keep the helper ergonomic — callers cast to the
 * expected signature.
 */
export function logOnly<T extends (...args: any[]) => any>(label: string): T {
  return ((...args: Parameters<T>) => {
    console.log(`[${label}]`, ...args);
  }) as T;
}
