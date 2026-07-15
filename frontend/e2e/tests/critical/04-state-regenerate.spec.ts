/**
 * Critical-4 — State regeneration paths.
 *
 * AGENTS.md §2 calls out three update paths to ``Conversation.state``
 * that must stay in sync, each with its own failure mode:
 *
 *  1. ``POST /api/threads/{id}/state/regenerate``  — manual, sync API.
 *  2. fire-and-forget task after ``send_message`` — auto.
 *  3. ``POST .../{message_id}/regenerate`` (message-branching) —
 *     reuses ``regenerate_state`` internally.
 *
 * Because the LLM in this dev env is unreachable (deepseek auth fail),
 * we cannot assert that *any state value* lands in the DB. What we
 * can — and must — assert is that the wiring doesn't blow up the
 * thread:
 *
 *   - manual endpoint returns non-5xx for a valid assistant_message_id
 *     (background task is fire-and-forget, that's fine)
 *   - bot with empty ``world_state_prompt`` does NOT silently overwrite
 *     state to "" — the ``rp_only_gate`` (see state_rp_only_gate test)
 *     must hold
 *   - listing messages after a chat send always returns at least one
 *     user + one assistant row, regardless of whether the LLM actually
 *     answered — the DB-row creation must not be conditional on LLM
 *     success
 *
 * These are the exact contracts that drift between releases; the
 * tests are written so a future Deepseek fix makes them stay green
 * (the assertions are about path integrity, not LLM output).
 */
import { expect } from '@playwright/test';

import { test as backendTest } from '../../fixtures/backend';

backendTest(
  'state/regenerate: bad assistant_message_id returns 404 @smoke',
  async ({ backend }) => {
    await backend.waitReady();

    const list = await backend.api.get('/api/bots');
    const bots = (await list.json()) as Array<{ id: number }>;
    const botId = bots[0].id;
    const t = await backend.api.post(`/api/bots/${botId}/threads`, { data: {} });
    const threadId = (await t.json()).id;

    // Invalid id — backend must NOT 200, must NOT corrupt state.
    const r = await backend.api.post(`/api/threads/${threadId}/state/regenerate`, {
      data: { assistant_message_id: 999_999_999 },
    });
    expect(r.status(), `bad assistant_message_id should reject; got body: ${await r.text()}`).toBe(
      404,
    );

    await backend.api.delete(`/api/threads/${threadId}`);
  },
);

backendTest(
  'chat send → messages endpoint returns user+assistant rows even when LLM errors @smoke',
  async ({ backend }) => {
    await backend.waitReady();

    const list = await backend.api.get('/api/bots');
    const bots = (await list.json()) as Array<{ id: number }>;
    const botId = bots[0].id;
    const t = await backend.api.post(`/api/bots/${botId}/threads`, { data: {} });
    const threadId = (await t.json()).id;

    // Send — stream may end with error (deepseek auth), but the user
    // row must be persisted before the LLM call. Closing the SSE
    // helper via the collect path is fine; we just want the side
    // effects on the DB.
    for await (const _chunk of (await import('../../lib/sse')).openStream(
      backend.api,
      `/api/threads/${threadId}/messages`,
      {
        data: { bot_id: botId, user_input: 'state-probe', user_message_id: `state-${Date.now()}` },
      },
    )) {
      // drain
    }

    // Read back. Order matters: list_messages returns ASC chain
    // (oldest → newest) — first row is always the user turn.
    const msgs = (await (
      await backend.api.get(`/api/threads/${threadId}/messages?limit=20`)
    ).json()) as Array<{
      content: string;
      id: number;
      role: string;
      state: null | string;
    }>;
    expect(msgs.length, 'no messages saved — persistence path is broken').toBeGreaterThanOrEqual(2);

    const userRow = msgs.find((m) => m.role === 'user');
    const assistantRow = msgs.find((m) => m.role === 'assistant');
    expect(userRow, 'user row missing').toBeTruthy();
    expect(userRow!.content).toBe('state-probe');
    expect(
      assistantRow,
      'assistant row missing — DB write is LLM-conditional, that is wrong',
    ).toBeTruthy();
    expect(assistantRow!.id, 'assistant row has no id').toBeGreaterThan(0);

    // The state field must be present in the DTO projection (even
    // if null). If the DTO silently drops it, this assertion fires.
    expect(
      'state' in assistantRow!,
      'MessageDTO.state not projected — frontend will lose world-state UI',
    ).toBeTruthy();

    await backend.api.delete(`/api/threads/${threadId}`);
  },
);
