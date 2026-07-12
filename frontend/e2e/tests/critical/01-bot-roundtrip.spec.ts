/**
 * Critical-1 — Bot create → list → DTO projection round trip.
 *
 * Why this matters (AGENTS.md §2): when a bot field is added,
 * the developer must update three places — Alembic migration,
 * SQLModel column, and DTO ``BotResponse.from_orm_bot``
 * projection. If any of the three is missing, the field is
 * silently dropped: SQL stays empty, ORM reads None, the
 * DTO returns "" or null, and the frontend never sees the
 * value. This spec exercises the same path the unit tests
 * exercise, but through the real HTTP boundary, which is the
 * only place all three pieces are guaranteed to be wired.
 *
 * Concretely: we POST a bot with every BotResponse field set
 * to a non-empty sentinel, GET it back, and assert that every
 * sentinel survived the round trip.
 */
import { test, expect } from '@playwright/test';
import { test as backendTest } from '../../fixtures/backend';

const UNIQUE = `e2e-rt-${Date.now()}`;
const SENTINELS = {
  name: `${UNIQUE}-name`,
  personality: `${UNIQUE}-personality`,
  first_message: `${UNIQUE}-first`,
  scenario: `${UNIQUE}-scenario`,
  description: `${UNIQUE}-description`,
  mes_example: `${UNIQUE}-mes`,
  dynamic_system_prompt: `${UNIQUE}-dyn`,
  world_state_prompt: `${UNIQUE}-world`,
};

backendTest('bot create → get → DTO round-trip preserves every field @smoke', async ({
  backend,
}) => {
  await backend.waitReady();

  // 1. Create
  const create = await backend.api.post('/api/bots', { data: SENTINELS });
  expect(create.ok(), `POST /api/bots failed: ${create.status()}`).toBeTruthy();
  const created = await create.json();
  const botId: number = created.id;
  expect(botId).toBeGreaterThan(0);

  // 2. Re-read — the moment of truth. If any of the 8 fields is
  // silently dropped by the DTO projection, this is where it
  // surfaces.
  const get = await backend.api.get(`/api/bots/${botId}`);
  expect(get.ok()).toBeTruthy();
  const dto = await get.json();

  for (const key of Object.keys(SENTINELS) as (keyof typeof SENTINELS)[]) {
    expect(dto[key], `BotResponse.${key} was not projected back`).toBe(SENTINELS[key]);
  }

  // 3. The DTO also flattens categories from a JSON column. Push a
  // non-empty category, expect it back as a list after a re-read.
  //
  // Note: POST /api/bots intentionally returns just {id: ...}; the
  // frontend follows up with GET /api/bots/{id} — which is also the
  // path the BotEditPage uses to populate the category picker on load.
  const withCat = await backend.api.post('/api/bots/categories', {
    data: { name: `${UNIQUE}-cat` },
  });
  expect(withCat.ok()).toBeTruthy();

  const created2 = await backend.api.post('/api/bots', {
    data: {
      ...SENTINELS,
      name: `${UNIQUE}-catbot`,
      categories: [`${UNIQUE}-cat`],
    },
  });
  expect(created2.ok()).toBeTruthy();
  const catId: number = (await created2.json()).id;

  const catGet = await backend.api.get(`/api/bots/${catId}`);
  expect(catGet.ok()).toBeTruthy();
  const catDto = await catGet.json();
  expect(catDto.categories, 'BotResponse.categories not projected from JSON column').toEqual([
    `${UNIQUE}-cat`,
  ]);

  // 4. Cleanup — these are throwaway bots, but the suite talks to a
  // shared database, so don't leave noise behind.
  await backend.api.delete(`/api/bots/${botId}`);
  await backend.api.delete(`/api/bots/${catId}`);
});

backendTest('update bot → re-read reflects new fields @smoke', async ({ backend }) => {
  await backend.waitReady();

  const create = await backend.api.post('/api/bots', {
    data: { ...SENTINELS, name: `${UNIQUE}-upd` },
  });
  const botId = (await create.json()).id;

  // Flip the personality sentinel. This goes through
  // ``UpdateBotRequest`` → repository → projection. If the
  // projection path on update is broken but not on create,
  // the test catches it.
  const NEW_PERSONALITY = `${UNIQUE}-upd-personality-v2`;
  const put = await backend.api.put(`/api/bots/${botId}`, {
    data: { ...SENTINELS, name: `${UNIQUE}-upd`, personality: NEW_PERSONALITY },
  });
  expect(put.ok(), `PUT /api/bots/${botId} failed: ${put.status()}`).toBeTruthy();

  const get = await backend.api.get(`/api/bots/${botId}`);
  const dto = await get.json();
  expect(dto.personality).toBe(NEW_PERSONALITY);

  await backend.api.delete(`/api/bots/${botId}`);
});
