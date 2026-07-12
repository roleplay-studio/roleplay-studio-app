/**
 * Real backend fixture.
 *
 * Spawns the actual FastAPI backend on 127.0.0.1:55245 with its own
 * scoped data directory. Default `webServer` in playwright.config.ts
 * already starts the backend, but we expose a `request` fixture that
 * talks to it directly so we can seed data via real REST calls (no
 * fakes — see AGENTS.md §2 "fake repos mask bugs").
 */
import { test as base, request as playwrightRequest, APIRequestContext } from '@playwright/test';

export type Backend = {
  api: APIRequestContext;
  baseUrl: string;
  /**
   * Wait until the backend is fully ready to accept LLM traffic.
   * Polls /api/setup/status — when it returns 200 with api_key_configured: true,
   * the chat endpoint is safe to hit.
   */
  waitReady: () => Promise<void>;
};

const BACKEND_PORT = 55245;
const BACKEND_BASE = `http://127.0.0.1:${BACKEND_PORT}`;

export const test = base.extend<{ backend: Backend }>({
  backend: async ({ playwright }, use) => {
    const api = await playwrightRequest.newContext({ baseURL: BACKEND_BASE });
    const backend: Backend = {
      api,
      baseUrl: BACKEND_BASE,
      waitReady: async () => {
        const deadline = Date.now() + 30_000;
        while (Date.now() < deadline) {
          try {
            const r = await api.get('/api/setup/status');
            if (r.ok()) return;
          } catch {
            // backend not yet listening — fall through
          }
          await new Promise((res) => setTimeout(res, 500));
        }
        throw new Error(`Backend at ${BACKEND_BASE} did not become ready within 30 s`);
      },
    };
    await use(backend);
    await api.dispose();
  },
});

export { expect } from '@playwright/test';
