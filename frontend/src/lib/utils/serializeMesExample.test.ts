// serializeMesExample.test.ts — vitest cases for the V2 mes_example serializer.

import { describe, expect, it } from 'vitest';

import { parseMesExample } from './parseMesExample';
import { serializeMesExample } from './serializeMesExample';

describe('serializeMesExample', () => {
  it('returns "" for empty dialogues', () => {
    expect(serializeMesExample([])).toBe('');
  });

  it('serializes a single dialogue with two turns', () => {
    const dialogues = [
      {
        turns: [
          { content: 'hi', role: 'user' as const },
          { content: 'hello', role: 'char' as const },
        ],
      },
    ];
    expect(serializeMesExample(dialogues)).toBe('<START>\n{{user}}: hi\n{{char}}: hello\n<END>');
  });

  it('joins multiple dialogues with blank line', () => {
    const dialogues = [
      { turns: [{ content: 'a', role: 'user' as const }] },
      { turns: [{ content: 'b', role: 'user' as const }] },
    ];
    expect(serializeMesExample(dialogues)).toBe(
      '<START>\n{{user}}: a\n<END>\n\n<START>\n{{user}}: b\n<END>',
    );
  });

  it('preserves multi-line content', () => {
    const dialogues = [{ turns: [{ content: 'line1\nline2', role: 'user' as const }] }];
    expect(serializeMesExample(dialogues)).toBe('<START>\n{{user}}: line1\nline2\n<END>');
  });

  it('round-trips with parseMesExample for spec-format input', () => {
    const raw = '<START>\n{{user}}: hi\n{{char}}: hello\n<END>';
    expect(serializeMesExample(parseMesExample(raw))).toBe(raw);
  });

  it('round-trips with multiple dialogues', () => {
    const raw = '<START>\n{{user}}: a\n{{char}}: b\n<END>\n\n<START>\n{{user}}: c\n<END>';
    expect(serializeMesExample(parseMesExample(raw))).toBe(raw);
  });

  it('normalizes <user>: / <bot>: markers to canonical {{user}}: / {{char}}:', () => {
    // parseMesExample accepts <user>: / <bot>:/<char>:. serializeMesExample
    // always emits the canonical {{user}}: / {{char}}: form.
    const inputRaw = '<START>\n<user>: hi\n<bot>: hello\n<END>';
    const expected = '<START>\n{{user}}: hi\n{{char}}: hello\n<END>';
    expect(serializeMesExample(parseMesExample(inputRaw))).toBe(expected);
  });
});
