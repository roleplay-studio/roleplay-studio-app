import { describe, expect, it } from 'vitest';

import { ApiError, BOT_TYPES } from '../api';

describe('ApiError', () => {
  it('sets status and detail', () => {
    const err = new ApiError(404, 'Not found');
    expect(err.status).toBe(404);
    expect(err.detail).toBe('Not found');
    expect(err.name).toBe('ApiError');
  });

  it('formats message correctly', () => {
    const err = new ApiError(500, 'Internal error');
    expect(err.message).toBe('API 500: Internal error');
  });
});

describe('BOT_TYPES', () => {
  it('has 3 bot types', () => {
    expect(BOT_TYPES).toHaveLength(3);
  });

  it('includes roleplay, assistant, and agent', () => {
    const values = BOT_TYPES.map((bt) => bt.value);
    expect(values).toContain('rp');
    expect(values).toContain('assistant');
    expect(values).toContain('agent');
  });

  it('each type has required fields', () => {
    for (const bt of BOT_TYPES) {
      expect(bt.label).toBeTruthy();
      expect(bt.description).toBeTruthy();
      expect(bt.icon).toBeTruthy();
    }
  });
});
