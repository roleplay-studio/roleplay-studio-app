import { describe, expect, it } from 'vitest';

import { formatRelativeTime } from '../time';

describe('formatRelativeTime', () => {
  it('returns empty string for null date', () => {
    expect(formatRelativeTime(null)).toBe('');
  });

  it('returns empty string for undefined-like falsy', () => {
    expect(formatRelativeTime('')).toBe('');
  });

  it('returns relative time in English by default', () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe('a few seconds ago');
  });

  it('returns relative time in Russian when lang=ru', () => {
    const now = new Date().toISOString();
    const result = formatRelativeTime(now, 'ru');
    expect(result).toMatch(/только что|несколько секунд/);
  });

  it('returns formatted date for dates >30 days ago', () => {
    const oldDate = '2024-01-15T12:00:00Z';
    const result = formatRelativeTime(oldDate);
    expect(result).toMatch(/^\w{3} \d+$/); // e.g. "Jan 15"
  });

  it('falls back to English for unknown lang code', () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now, 'de')).toBe('a few seconds ago');
  });

  it('handles 2 minutes ago', () => {
    const twoMinAgo = new Date(Date.now() - 2 * 60 * 1000).toISOString();
    const result = formatRelativeTime(twoMinAgo);
    expect(result).toMatch(/2 minutes ago|a few seconds ago/);
  });
});
