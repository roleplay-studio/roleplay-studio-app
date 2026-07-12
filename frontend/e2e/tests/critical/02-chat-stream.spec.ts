/**
 * Critical-2 — Chat SSE stream envelope shape.
 *
 * The chat UI is built around the streaming protocol (verified
 * by reading ``Chat.svelte:594``):
 *   1. First event is {type: 'meta', thread_id}.
 *   2. Then {type: 'debug', debug: {messages, …}} — snapshot of
 *      what was actually sent to the LLM (only with DEBUG=true).
 *   3. Reasoning tokens arrive as a run of
 *      {type: 'reasoning', content} chunks (skip if model has
 *      no thinking).
 *   4. Visible reply is a sequence of {type: 'chunk', content}
 *      tokens whose concatenation forms the assistant message.
 *   5. On error the backend emits {type: 'error', detail}
 *      instead of chunks — must not silently truncate.
 *   6. Stream always ends with the sentinel data: [DONE].
 *
 * The SSE helper in ``lib/sse.ts`` translates ``[DONE]`` into a
 * ``done: true`` chunk so callers don't have to remember the
 * raw protocol.
 *
 * If any of these contracts breaks, the chat UI hangs, loses
 * tokens, or shows an empty assistant bubble. We exercise the
 * real endpoint (no MSW, no mocked SSE) so wiring bugs surface
 * here, not at midnight during a hot fix.
 *
 * AGENTS.md §2 warning: fakes that "model the SSE contract"
 * historically missed race conditions (e.g. error arriving
 * before done). The only way to be sure is to talk to the real
 * endpoint and inspect chunks in order.
 */
import { test, expect } from '@playwright/test';
import { test as backendTest } from '../../fixtures/backend';
import { collectUntil, openStream } from '../../lib/sse';

backendTest('SSE envelope: meta first, then chunk/error, then done @smoke', async ({
  backend,
}) => {
  await backend.waitReady();

  // Pick the first existing bot — we don't seed a fresh one because
  // every chat-SSE run costs a real LLM call.
  const list = await backend.api.get('/api/bots');
  expect(list.ok()).toBeTruthy();
  const bots = (await list.json()) as Array<{ id: number }>;
  expect(bots.length).toBeGreaterThan(0);
  const botId = bots[0].id;

  const t = await backend.api.post(`/api/bots/${botId}/threads`, { data: {} });
  expect(t.ok()).toBeTruthy();
  const threadId = (await t.json()).id;

  const events: Array<{ type: string; payload: unknown }> = [];
  let sawDone = false;
  let sawMeta = false;
  let sawProgress = false;

  for await (const chunk of openStream(backend.api, `/api/threads/${threadId}/messages`, {
    data: { bot_id: botId, user_input: 'ping', user_message_id: `e2e-stream-${Date.now()}` },
  })) {
    if (chunk.done) {
      sawDone = true;
      events.push({ type: 'done', payload: null });
      break;
    }
    const payload = chunk.data as { type: string } | null;
    expect(payload?.type, 'every SSE chunk is missing a `type` field').toBeTruthy();
    events.push({ type: payload!.type, payload });

    if (payload!.type === 'meta') sawMeta = true;
    // Either the LLM streamed chunks of reasoning/content, or
    // it errored out (auth fail, network glitch). Both are
    // legitimate progress signals for the UI.
    if (
      payload!.type === 'chunk' ||
      payload!.type === 'reasoning' ||
      payload!.type === 'error'
    ) {
      sawProgress = true;
    }
  }

  // Contract checks in order.
  expect(sawMeta, 'SSE stream must start with a meta event').toBeTruthy();
  expect(sawProgress, 'SSE stream must include chunk/reasoning/error before done').toBeTruthy();
  expect(sawDone, 'SSE stream must end with a done sentinel').toBeTruthy();

  // The first event is canonical: it must be `meta`. Anything
  // before it leaks the LLM thread id etc.
  expect(events[0].type, 'first SSE event must be "meta"').toBe('meta');

  // Cleanup — drop the throwaway thread so we don't pollute the
  // dashboard for subsequent runs.
  await backend.api.delete(`/api/threads/${threadId}`);
});

backendTest('SSE body is parseable line by line (no chunked-stream corruption) @smoke', async ({
  backend,
}) => {
  await backend.waitReady();
  const list = await backend.api.get('/api/bots');
  const bots = (await list.json()) as Array<{ id: number }>;
  const botId = bots[0].id;
  const t = await backend.api.post(`/api/bots/${botId}/threads`, { data: {} });
  const threadId = (await t.json()).id;

  // collectUntil returns the concatenated assistant text (from
  // ``chunk`` events with ``content``), or '' if the LLM was
  // unavailable / errored. Either is acceptable — what we want
  // to know is that ``openStream`` parsed the bytes without
  // throwing. The real LLM is best-effort: this test asserts
  // the protocol stability, not the model quality.
  const text = await collectUntil(backend.api, `/api/threads/${threadId}/messages`, {
    minChars: 1,
    payload: {
      bot_id: botId,
      user_input: 'say one word',
      user_message_id: `e2e-stream-collect-${Date.now()}`,
    },
  });
  expect(typeof text).toBe('string');

  await backend.api.delete(`/api/threads/${threadId}`);
});
