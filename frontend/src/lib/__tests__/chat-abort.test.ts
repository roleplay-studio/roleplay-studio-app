import { afterEach, describe, expect, it, vi } from 'vitest';

import { api } from '../api';

/**
 * Locks in the api.abortGeneration contract — frontend uses this to kill
 * the server-side LLM task when the user clicks Stop. The 200/204 paths
 * are the only success outcomes; anything else throws.
 */

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('api.abortGeneration', () => {
  it('POSTs to /api/threads/{id}/abort and returns was_active on 200', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ partial_saved: true, was_active: true }),
      ok: true,
      status: 200,
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await api.abortGeneration(42);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/threads/42/abort');
    expect(init).toMatchObject({ method: 'POST' });
    expect(result).toEqual({ partial_saved: true, was_active: true });
  });

  it('returns was_active=false on 204 No Content (idempotent no-op)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => {
        throw new Error('no body for 204');
      },
      ok: true,
      status: 204,
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await api.abortGeneration(99);

    expect(result).toEqual({ partial_saved: false, was_active: false });
  });

  it('throws on non-2xx responses (other than 204)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ detail: 'internal error' }),
      ok: false,
      status: 500,
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await expect(api.abortGeneration(7)).rejects.toThrow(/abort failed: 500/);
  });
});
