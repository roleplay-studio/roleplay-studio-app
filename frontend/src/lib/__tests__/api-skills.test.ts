/**
 * Tests for the Skills API surface in api.ts. Phase 5 / Task 14.
 *
 * Covers the public shape that downstream UI code (BotEditPage,
 * SkillsLibraryPage) will consume — types, ApiError extension for
 * the 409 path, and the runtime contract of `deleteSkill`.
 */
import { describe, expect, it } from 'vitest';

import {
  api,
  ApiError,
  type BotSkillDTO,
  type CreateSkillCommand,
  type SkillDTO,
  type UpdateSkillCommand,
} from '../api';

describe('Skills: type surface', () => {
  it('exposes SkillDTO with required fields', () => {
    const skill: SkillDTO = {
      created_at: '2026-07-17T00:00:00Z',
      description: 'dry wit',
      id: 1,
      instruction: 'Apply when user opens with sarcasm',
      name: 'Sarcastic',
      tags: ['tone', 'dialog'],
      updated_at: '2026-07-17T00:00:00Z',
    };
    expect(skill.id).toBe(1);
    expect(skill.tags).toEqual(['tone', 'dialog']);
  });

  it('exposes CreateSkillCommand with required name+instruction', () => {
    const cmd: CreateSkillCommand = {
      description: 'a desc',
      instruction: 'do this',
      name: 'Sarcastic',
      tags: ['tone'],
    };
    expect(cmd.name).toBe('Sarcastic');
    expect(cmd.tags).toHaveLength(1);
  });

  it('exposes UpdateSkillCommand with all-optional fields', () => {
    const partial: UpdateSkillCommand = { description: 'updated' };
    expect(partial.description).toBe('updated');
    expect(partial.name).toBeUndefined();
  });

  it('exposes BotSkillDTO as slim projection', () => {
    const botSkill: BotSkillDTO = {
      description: 'dry wit',
      id: 1,
      name: 'Sarcastic',
    };
    // BotSkillDTO does NOT carry instruction or tags.
    expect(botSkill).not.toHaveProperty('instruction');
    expect(botSkill).not.toHaveProperty('tags');
  });
});

describe('ApiError: attached_to for 409 Conflict', () => {
  it('carries attached_to when supplied', () => {
    const err = new ApiError(409, 'in use', [3, 7, 11]);
    expect(err.status).toBe(409);
    expect(err.detail).toBe('in use');
    expect(err.attached_to).toEqual([3, 7, 11]);
  });

  it('omits attached_to when not supplied', () => {
    const err = new ApiError(404, 'not found');
    expect(err.attached_to).toBeUndefined();
  });
});

describe('api.deleteSkill: 409 conflict propagation', () => {
  it('throws ApiError with attached_to on 409', async () => {
    // Stub fetch globally so we don't hit the real backend.
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (_url: Request | string | URL) => {
      return new Response(
        JSON.stringify({
          attached_to: [3, 7, 11],
          detail: 'Skill 1 is attached to 3 bot(s)',
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 409,
        }
      ) as Response;
    }) as typeof fetch;

    try {
      await expect(api.deleteSkill(1)).rejects.toMatchObject({
        attached_to: [3, 7, 11],
        detail: expect.stringContaining('attached to 3'),
        status: 409,
      });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('returns true on 204 No Content', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (_url: Request | string | URL) => {
      return new Response(null, { status: 204 }) as Response;
    }) as typeof fetch;

    try {
      const result = await api.deleteSkill(42);
      expect(result).toBe(true);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

describe('api.listSkills: query parameters', () => {
  it('builds URL with q and tag when both provided', () => {
    // Spy on fetch to capture the URL the client requests.
    let capturedUrl = '';
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: Request | string | URL) => {
      capturedUrl = typeof url === 'string' ? url : url.toString();
      return new Response(JSON.stringify([]), {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      }) as Response;
    }) as typeof fetch;

    return api
      .listSkills('sarcastic', 'tone')
      .then(() => {
        expect(capturedUrl).toContain('/api/skills?');
        expect(capturedUrl).toContain('q=sarcastic');
        expect(capturedUrl).toContain('tag=tone');
      })
      .finally(() => {
        globalThis.fetch = originalFetch;
      });
  });

  it('omits query string when both params undefined', () => {
    let capturedUrl = '';
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: Request | string | URL) => {
      capturedUrl = typeof url === 'string' ? url : url.toString();
      return new Response(JSON.stringify([]), {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      }) as Response;
    }) as typeof fetch;

    return api
      .listSkills()
      .then(() => {
        expect(capturedUrl).toContain('/api/skills');
        expect(capturedUrl).not.toContain('?');
      })
      .finally(() => {
        globalThis.fetch = originalFetch;
      });
  });
});