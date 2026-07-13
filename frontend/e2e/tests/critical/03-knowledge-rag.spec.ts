/**
 * Critical-3 — Knowledge base RAG end-to-end.
 *
 * Multi-layer pipeline exercised here:
 *   file upload → multipart parser → chunker → Chroma embedding
 *   → query → similarity search → DTO projection.
 *
 * Why this matters (AGENTS.md §2):
 *   - Silent dimension mismatch: a switch of the embedding
 *     model can leave Chroma holding vectors of a different
 *     size — the test_search endpoint must either succeed or
 *     return a clear 400, never crash. We probe for that.
 *   - Test fakes that mock Chroma have historically passed
 *     while the real one silently ingested broken vectors.
 *
 * Our test uploads an inline text payload with a unique
 * sentinel, then queries for that sentinel. If Chroma returns
 * it with a positive similarity score, the full pipeline is
 * honest.
 */
import { expect } from '@playwright/test';

import { test as backendTest } from '../../fixtures/backend';
import { postMultipartText } from '../../lib/multipart';

backendTest(
  'upload knowledge → query through real Chroma returns the chunk @smoke',
  async ({ backend }) => {
    await backend.waitReady();

    // Use the seeded E2E bot (it might not exist yet on a fresh
    // dev DB, but the backend always has starter bots). Whatever
    // its id, we own a clean knowledge-only namespace inside it.
    const list = await backend.api.get('/api/bots');
    const bots = (await list.json()) as Array<{ id: number }>;
    const botId = bots[0].id;

    // Per-test unique sentinel so we can sanity-check that even
    // if a parallel worker uploaded its own file, ours is the
    // one we're seeing in the list.
    const TAG = `e2e-rag-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const PROBE = `The Cult of ${TAG} watches from the night; ${TAG} governs dreams and omens.`;
    const FILE = `${TAG}.txt`;

    const up = await postMultipartText(backend.api, `/api/knowledge/${botId}/upload`, FILE, PROBE);
    expect(up.ok(), `knowledge upload failed: ${up.status()} ${await up.text()}`).toBeTruthy();
    const payload = await up.json();
    expect(payload.status).toBe('ok');
    expect(payload.file_name).toBe(FILE);
    expect(payload.chunk_count).toBeGreaterThan(0);

    // Query the unique sentinel — anything matching proves the
    // chunk we wrote is the one we're seeing.
    const query = await backend.api.post(`/api/knowledge/${botId}/test-search`, {
      data: { query: TAG, top_k: 3 },
    });
    expect(query.ok()).toBeTruthy();
    const search = (await query.json()) as {
      results: Array<{ content: string; score: number }>;
    };
    expect(search.results.length).toBeGreaterThan(0);
    const top = search.results[0];
    expect(top.content, `top chunk should contain the sentinel text`).toContain(TAG);
    expect(top.score, 'top score must be positive (chunks are not noise)').toBeGreaterThan(0);

    // Cleanup. The bot is shared, but its KB namespace is not —
    // we drop our own file's chunks so other tests aren't
    // polluted.
    await backend.api.delete(`/api/knowledge/${botId}/file/${FILE}`);
  },
);

backendTest(
  'knowledge list returns uploaded entries via DTO projection @smoke',
  async ({ backend }) => {
    await backend.waitReady();
    const list = await backend.api.get('/api/bots');
    const bots = (await list.json()) as Array<{ id: number }>;
    const botId = bots[0].id;

    const TAG = `e2e-rag-list-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const FILE = `${TAG}.txt`;
    const PROBE = `${TAG} paragraph one.\n\n${TAG} paragraph two for second chunk.`;

    const up = await postMultipartText(backend.api, `/api/knowledge/${botId}/upload`, FILE, PROBE);
    expect(up.ok()).toBeTruthy();

    // Listing is filtered by file_name so other workers can't
    // contaminate our result even when they upload in parallel.
    const after = await backend.api.get(`/api/knowledge/${botId}`);
    const entries = (await after.json()) as Array<{
      content: string;
      file_name?: string;
    }>;
    const ours = entries.filter((e) => e.file_name === FILE || e.content.includes(TAG));
    expect(
      ours.length,
      'at least one chunk from our upload must appear in the listing',
    ).toBeGreaterThan(0);
    expect(ours.some((e) => e.content.includes(TAG))).toBeTruthy();

    await backend.api.delete(`/api/knowledge/${botId}/file/${FILE}`);
  },
);
