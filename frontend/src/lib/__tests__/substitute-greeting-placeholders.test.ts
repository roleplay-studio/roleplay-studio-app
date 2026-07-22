import { describe, expect, it } from 'vitest';

import { substituteGreetingPlaceholders } from '../utils/substitute-greeting-placeholders';

describe('substituteGreetingPlaceholders', () => {
  it('replaces every occurrence of {{user}} with the persona name', () => {
    const greeting = 'Hi {{user}}! Welcome back, {{user}}.';
    const result = substituteGreetingPlaceholders(greeting, 'Alice');
    expect(result).toBe('Hi Alice! Welcome back, Alice.');
  });

  it('leaves the text untouched when no persona is selected', () => {
    const greeting = 'Hi {{user}}! Welcome back, {{user}}.';
    // No persona → orchestrator will substitute on the first turn
    // and a later persona change can still re-substitute without
    // the old name being baked in. Same as the backend.
    expect(substituteGreetingPlaceholders(greeting, null)).toBe(greeting);
  });

  it('treats empty persona name as no-op (does not wipe the placeholder)', () => {
    const greeting = 'Hi {{user}}!';
    // Better to let the LLM see {{user}} than to lose the name entirely.
    expect(substituteGreetingPlaceholders(greeting, '')).toBe(greeting);
  });

  it('passes through text that has no placeholder', () => {
    const greeting = 'Welcome to the tavern, friend.';
    expect(substituteGreetingPlaceholders(greeting, 'Alice')).toBe(
      'Welcome to the tavern, friend.',
    );
  });

  it('returns empty string unchanged', () => {
    expect(substituteGreetingPlaceholders('', 'Alice')).toBe('');
  });

  it('handles a single placeholder without spurious extra replacements', () => {
    const greeting = '{{user}}';
    expect(substituteGreetingPlaceholders(greeting, 'Bob')).toBe('Bob');
  });

  it('does not touch non-{{user}} tokens like {{char}}', () => {
    // {{char}} is for the bot name, handled separately on the
    // backend. The frontend helper is intentionally narrow —
    // substituting {{char}} here would require the bot's display
    // name and is out of scope for the runtime UI fix.
    const greeting = 'I am {{char}} and you are {{user}}.';
    expect(substituteGreetingPlaceholders(greeting, 'Alice')).toBe(
      'I am {{char}} and you are Alice.',
    );
  });
});
