/**
 * Deterministic seed data for E2E tests.
 *
 * Hits the real backend endpoints to populate DB state. Why not
 * INSERT INTO … directly? Because:
 *   1. Real services run validation, normalize names, generate
 *      timestamps, build relationships. Bypassing them with raw SQL
 *      leaves state the application has never seen.
 *   2. Chroma collections are created lazily — direct INSERT without
 *      the service leaves dangling references.
 *   3. AGENTS.md §2 explicitly warns that test fakes that "model the
 *      SQL contract" can diverge from real behaviour.
 *
 * The seed is intentionally small: 1 category, 1 persona, 2 bots,
 * 2 threads. Each test extends via the real API as needed; this is
 * the canonical baseline.
 *
 * Real endpoints verified by reading api/routes/* on 2026-07-09:
 *   POST /api/bots                      → CreateBotCommand
 *   POST /api/bots/categories           → CategoryAddRequest
 *   POST /api/bots/{bot_id}/threads     → returns {"id": thread_id}
 *   POST /api/personas                  → CreatePersonaCommand
 *   POST /api/threads/{tid}/messages    → ChatRequest (SSE streaming)
 */
import type { APIRequestContext } from '@playwright/test';

export type SeedSummary = {
  botIds: number[];
  categoryName: string;
  personaId: number;
  threadIds: number[];
};

const AYA_NAME = 'Aya';
const AYA_DESC = 'A reflective companion for evening conversations.';

const BOT_LUNA = {
  description: 'A nightly companion for quiet reflection.',
  first_message: 'Welcome, traveler. What weighs on your mind tonight?',
  name: 'E2E-Luna',
  personality: 'A serene dreamer who speaks in soft metaphors.',
  scenario: 'A moonlit study filled with old books.',
};

const BOT_KAI = {
  description: 'Daytime companion — sharp, casual, encyclopedic about beans.',
  first_message: 'Hey, what are you drinking?',
  name: 'E2E-Kai',
  personality: 'A direct, witty barista with strong opinions about coffee.',
  scenario: 'A specialty coffee bar on a busy morning.',
};

/**
 * Convenience: open a chat stream against an existing thread. Used by
 * integration tests to validate SSE wiring without going through UI.
 */
export async function postMessage(
  api: APIRequestContext,
  threadId: number,
  content: string,
  userMessageId?: string,
) {
  return api.post(`/api/threads/${threadId}/messages`, {
    data: { content, user_message_id: userMessageId },
  });
}

export async function seedViaApi(api: APIRequestContext): Promise<SeedSummary> {
  // 1. Category — list, dedupe, append
  const catName = 'E2E-Category';
  await api.post('/api/bots/categories', { data: { name: catName } });
  // The dedup-tolerant endpoint returns the full list; ignore the result.

  // 2. Persona
  const personaResp = await api.post('/api/personas', {
    data: { description: AYA_DESC, name: AYA_NAME },
  });
  if (!personaResp.ok()) {
    throw new Error(`persona create failed: ${personaResp.status()} ${await personaResp.text()}`);
  }
  const persona = await personaResp.json();

  // 3. Bots — POST /api/bots returns {"id": int}
  const lunaId = await createBot(api, BOT_LUNA);
  const kaiId = await createBot(api, BOT_KAI);

  // 4. Threads — one per bot
  const t1Id = await createThread(api, lunaId);
  const t2Id = await createThread(api, kaiId);

  return {
    botIds: [lunaId, kaiId],
    categoryName: catName,
    personaId: persona.id,
    threadIds: [t1Id, t2Id],
  };
}

async function createBot(api: APIRequestContext, body: typeof BOT_LUNA): Promise<number> {
  const r = await api.post('/api/bots', { data: body });
  if (!r.ok()) throw new Error(`createBot ${body.name} failed: ${r.status()} ${await r.text()}`);
  const j = await r.json();
  return j.id;
}

async function createThread(api: APIRequestContext, botId: number): Promise<number> {
  const r = await api.post(`/api/bots/${botId}/threads`, { data: {} });
  if (!r.ok())
    throw new Error(`createThread for bot ${botId} failed: ${r.status()} ${await r.text()}`);
  const j = await r.json();
  return j.id;
}
