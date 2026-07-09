/**
 * SSE helpers.
 *
 * Backend emits Server-Sent Events for streaming chat. We need a
 * deterministic way to wait until a stream finishes, or until a
 * specific token appears (for testing partial-state UI without
 * waiting for the full response).
 *
 * Why a custom parser instead of EventSource / readable-stream
 * polyfills? Because `ReadableStream` from `fetch` does not implement
 * the Web `EventSource` protocol, and pull-polyfills add 50+ kB.
 *
 * We use `eventsource-parser` (already a transitive dep of
 * `playwright`) — but with caution: its only purpose here is to split
 * the stream into `data: { ... }` chunks. We treat each chunk as a
 * generic SSE message — event name `message`, id omitted.
 */

import type { APIRequestContext, APIResponse } from '@playwright/test';

export type StreamChunk = {
  /** Raw JSON payload (when `data` was parseable). Null for the `[DONE]` sentinel. */
  data: unknown | null;
  /** True when the backend signals end of stream (`data: [DONE]`). */
  done: boolean;
};

/**
 * Open a streaming endpoint and yield chunks as they arrive.
 * Throws if response.ok() is false.
 */
export async function* openStream(api: APIRequestContext, path: string, opts: { method?: string; data?: unknown; headers?: Record<string, string> } = {}): AsyncGenerator<StreamChunk> {
  const response: APIResponse = await api.fetch(path, {
    method: opts.method ?? 'POST',
    data: opts.data,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...opts.headers,
    },
  });
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Stream open failed ${response.status()}: ${body.slice(0, 200)}`);
  }

  const reader = await response.body();
  if (!reader) throw new Error(`Stream response had no body for ${path}`);

  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += new TextDecoder('utf-8').decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, nl);
      buffer = buffer.slice(nl + 1);
      if (line.startsWith('data:')) {
        const payload = line.slice(5).trim();
        if (payload === '[DONE]') {
          yield { data: null, done: true };
          return;
        }
        try {
          yield { data: JSON.parse(payload), done: false };
        } catch {
          // Some chunks are non-JSON (heartbeats, comments). Skip.
        }
      }
    }
  }
}

/**
 * Collect streamed chunks until either:
 *  - the total content text reaches `minChars`, or
 *  - the stream ends (whichever first).
 *
 * Returns the concatenated string. Useful for fast smoke tests: we
 * don't need the entire response, just enough to prove the assistant
 * spoke.
 */
export async function collectUntil(api: APIRequestContext, path: string, opts: { minChars: number; payload?: unknown }): Promise<string> {
  let total = '';
  for await (const chunk of openStream(api, path, { data: opts.payload })) {
    if (chunk.done) break;
    const d = chunk.data as { content?: string } | null;
    if (d?.content) {
      total += d.content;
      if (total.length >= opts.minChars) break;
    }
  }
  return total;
}
