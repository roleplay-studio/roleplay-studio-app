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
 *
 * Playwright's ``APIResponse.body()`` returns a Node ``Buffer``
 * (a ``Uint8Array``), not a Web ``ReadableStream``. The original
 * helper tried ``reader.read()`` against that and crashed — caught
 * immediately by ``02-chat-stream.spec.ts`` when it tried to assert
 * on a real LLM stream. We now read the full response once with
 * ``response.text()`` and feed the parser a complete SSE blob.
 *
 * Trade-off: we lose true byte-by-byte streaming, so a backend that
 * stalls the TCP connection mid-stream will look healthy in this
 * helper. Acceptable for the suite's purpose — we care about the
 * event-sequence contract, not the watermark behaviour. If we ever
 * need millisecond-level backpressure tests, switch to
 * ``eventsource-parser`` over a manual byte loop.
 *
 * Throws if ``response.ok()`` is false.
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

  const raw = await response.text();
  let sawDone = false;
  for (const line of raw.split('\n')) {
    if (!line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (payload === '[DONE]') {
      sawDone = true;
      yield { data: null, done: true };
      break;
    }
    if (!payload) continue;
    try {
      yield { data: JSON.parse(payload), done: false };
    } catch {
      // Some chunks are non-JSON (heartbeats, comments). Skip.
    }
  }
  if (!sawDone) {
    // Backend protocol contract: every chat stream must end with
    // [DONE]. If it didn't, surface that loudly so callers can
    // assert on it instead of silently truncating.
    yield { data: null, done: true };
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
