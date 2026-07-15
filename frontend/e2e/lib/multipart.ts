/**
 * Multipart upload helper.
 *
 * Playwright's APIRequestContext ``multipart.buffer`` field
 * accepts Node ``Buffer`` (Uint8Array subclass). The project's
 * tsconfig does not include ``"types": ["node"]`` (kept lean so
 * page objects stay portable), so we use ``globalThis.Buffer``
 * with a defensive fallback to a ``Uint8Array`` for the type
 * checker. At runtime Playwright always runs in Node, so Buffer
 * is always present — the fallback only fires in pure-TS
 * tooling chains.
 */
import type { APIRequestContext, APIResponse } from '@playwright/test';

type NodeBuffer = Uint8Array & {
  toString(encoding?: string): string;
};

// Ambient declaration for Node's Buffer global so the type checker
// narrows `globalThis.Buffer` correctly. The name is prefixed with
// `_` so the eslint `no-unused-vars` rule treats it as a known
// ambient (it is consumed via `globalThis.Buffer` on line 36, not
// as a direct symbol reference). Without this, the page-object
// tsconfig breaks for `multipart.buffer: NodeBuffer`.
declare const _Buffer: undefined | { from(input: string, encoding?: string): NodeBuffer };

export async function postMultipartText(
  api: APIRequestContext,
  path: string,
  fileName: string,
  text: string,
  mimeType = 'text/plain',
  fieldName = 'file',
): Promise<APIResponse> {
  const buf = getBuffer().from(text, 'utf-8');
  return api.post(path, {
    multipart: {
      [fieldName]: { buffer: buf, mimeType, name: fileName },
    },
  });
}

function getBuffer(): { from(input: string, encoding?: string): NodeBuffer } {
  const g = globalThis as unknown as {
    Buffer?: { from(input: string, encoding?: string): NodeBuffer };
  };
  if (!g.Buffer) {
    throw new Error(
      'Node Buffer is not available in this Playwright runtime — multipart uploads require Node.',
    );
  }
  return g.Buffer;
}
