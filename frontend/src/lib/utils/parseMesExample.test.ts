// parseMesExample.test.ts — vitest cases for the V2 mes_example parser.

import { describe, expect, it } from 'vitest';

import { parseMesExample } from './parseMesExample';

describe('parseMesExample', () => {
  it('returns [] for empty string', () => {
    expect(parseMesExample('')).toEqual([]);
  });

  it('returns [] for whitespace-only string', () => {
    expect(parseMesExample('   \n  ')).toEqual([]);
  });

  it('parses a single dialogue with two turns', () => {
    const raw = '<START>\n{{user}}: hi\n{{char}}: hello\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'hi', role: 'user' },
          { content: 'hello', role: 'char' },
        ],
      },
    ]);
  });

  it('parses multiple dialogues', () => {
    const raw = '<START>\n{{user}}: a\n{{char}}: b\n<END>\n\n<START>\n{{user}}: c\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'a', role: 'user' },
          { content: 'b', role: 'char' },
        ],
      },
      { turns: [{ content: 'c', role: 'user' }] },
    ]);
  });

  it('handles <user>: and <bot>: alternate markers', () => {
    const raw = '<START>\n<user>: hi\n<bot>: hello\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'hi', role: 'user' },
          { content: 'hello', role: 'char' },
        ],
      },
    ]);
  });

  it('joins multi-line turns', () => {
    const raw = '<START>\n{{user}}: line1\n  line2\n{{char}}: response\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'line1\n  line2', role: 'user' },
          { content: 'response', role: 'char' },
        ],
      },
    ]);
  });

  it('ignores text outside <START>...<END> blocks', () => {
    const raw = 'Some intro text.\n<START>\n{{user}}: hi\n<END>\nTrailing text.';
    expect(parseMesExample(raw)).toEqual([{ turns: [{ content: 'hi', role: 'user' }] }]);
  });

  it('matches orphan <START> blocks that lack <END> (fallback)', () => {
    // Some character card authors omit <END>. The parser now falls
    // back to matching <START> up to EOF so those examples still
    // render in the visual editor instead of silently disappearing.
    const raw = '<START>\n{{user}}: orphan\nNo END here';
    expect(parseMesExample(raw)).toEqual([
      { turns: [{ content: 'orphan\nNo END here', role: 'user' }] },
    ]);
  });

  it('matches <START> followed by another <START> (no <END>)', () => {
    const raw = '<START>\n{{user}}: first\n<START>\n{{user}}: second\n<END>';
    expect(parseMesExample(raw)).toEqual([
      { turns: [{ content: 'first', role: 'user' }] },
      { turns: [{ content: 'second', role: 'user' }] },
    ]);
  });

  it('normalizes Windows line endings inside blocks', () => {
    const raw = '<START>\r\n{{user}}: hi\r\n{{char}}: hello\r\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'hi', role: 'user' },
          { content: 'hello', role: 'char' },
        ],
      },
    ]);
  });

  it('is case-insensitive on {{User}} and {{CHAR}} markers', () => {
    const raw = '<START>\n{{User}}: hi\n{{CHAR}}: hello\n<END>';
    expect(parseMesExample(raw)).toEqual([
      {
        turns: [
          { content: 'hi', role: 'user' },
          { content: 'hello', role: 'char' },
        ],
      },
    ]);
  });
});
