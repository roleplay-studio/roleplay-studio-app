import { describe, expect, it } from 'vitest';

import {
  canSortGreeting,
  loadGreetings,
  MAX_GREETINGS,
  saveGreetings,
  sortGreeting,
} from '../utils/edit-greetings';

describe('loadGreetings', () => {
  it('stitches first_message and alternate_greetings into one list', () => {
    expect(loadGreetings('Hello!', ['Hi!', 'Hey!'])).toEqual(['Hello!', 'Hi!', 'Hey!']);
  });

  it('returns a one-element list when no alternates exist', () => {
    expect(loadGreetings('Just first', [])).toEqual(['Just first']);
  });

  it('handles empty first_message and empty alternates', () => {
    expect(loadGreetings('', [])).toEqual(['']);
  });
});

describe('saveGreetings', () => {
  it('splits a list back into first_message and alternate_greetings', () => {
    expect(saveGreetings(['A', 'B', 'C'])).toEqual({
      alternate_greetings: ['B', 'C'],
      first_message: 'A',
    });
  });

  it('handles a single-element list (only the first message)', () => {
    expect(saveGreetings(['Only'])).toEqual({
      alternate_greetings: [],
      first_message: 'Only',
    });
  });

  it('handles an empty list (returns empty first_message, no alts)', () => {
    expect(saveGreetings([])).toEqual({
      alternate_greetings: [],
      first_message: '',
    });
  });

  it('round-trips with loadGreetings', () => {
    const original = { alts: ['Y', 'Z'], first: 'X' };
    const stitched = loadGreetings(original.first, original.alts);
    const split = saveGreetings(stitched);
    expect(split).toEqual({
      alternate_greetings: original.alts,
      first_message: original.first,
    });
  });
});

describe('MAX_GREETINGS', () => {
  it('is 10 (1 first + 9 alternates)', () => {
    expect(MAX_GREETINGS).toBe(10);
  });
});

describe('sortGreeting', () => {
  it('moves a greeting up by swapping with the previous one', () => {
    expect(sortGreeting(['A', 'B', 'C'], 1, 'up')).toEqual(['B', 'A', 'C']);
  });

  it('moves a greeting down by swapping with the next one', () => {
    expect(sortGreeting(['A', 'B', 'C'], 1, 'down')).toEqual(['A', 'C', 'B']);
  });

  it('moves the first greeting up to the top (no-op at index 0)', () => {
    // Per spec: free sorting is allowed, but index 0 can't go higher.
    expect(sortGreeting(['A', 'B', 'C'], 0, 'up')).toEqual(['A', 'B', 'C']);
  });

  it('moves the last greeting down (no-op at the end)', () => {
    expect(sortGreeting(['A', 'B', 'C'], 2, 'down')).toEqual(['A', 'B', 'C']);
  });

  it('returns a new array — does not mutate the input', () => {
    const input = ['A', 'B', 'C'];
    const out = sortGreeting(input, 0, 'down');
    expect(input).toEqual(['A', 'B', 'C']);
    expect(out).not.toBe(input);
  });
});

describe('canSortGreeting', () => {
  it('disables up on the first element', () => {
    expect(canSortGreeting(0, 'up', 3)).toBe(false);
  });

  it('enables up on any non-first element', () => {
    expect(canSortGreeting(1, 'up', 3)).toBe(true);
    expect(canSortGreeting(2, 'up', 3)).toBe(true);
  });

  it('disables down on the last element', () => {
    expect(canSortGreeting(2, 'down', 3)).toBe(false);
  });

  it('enables down on any non-last element', () => {
    expect(canSortGreeting(0, 'down', 3)).toBe(true);
    expect(canSortGreeting(1, 'down', 3)).toBe(true);
  });

  it('disables both for a single-element list', () => {
    expect(canSortGreeting(0, 'up', 1)).toBe(false);
    expect(canSortGreeting(0, 'down', 1)).toBe(false);
  });
});
