import { describe, expect, it } from 'vitest';

import { parseMessageContent } from '../utils/parseMetadata';

describe('parseMessageContent', () => {
  it('returns original content when no separator', () => {
    const r = parseMessageContent('Hello world');
    expect(r.mainContent).toBe('Hello world');
    expect(r.stats).toBeNull();
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
  });

  it('parses key:value lines as stats', () => {
    const r = parseMessageContent(
      'You find a treasure chest.\n---\nHP: 10\nGOLD: 20000\nDEATH: 15',
    );
    expect(r.mainContent).toBe('You find a treasure chest.');
    expect(r.stats).toHaveLength(3);
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.stats![0]).toMatchObject({ isNumeric: true, key: 'hp', value: 10 });
    expect(r.stats![1]).toMatchObject({ isNumeric: true, key: 'gold', value: 20000 });
    expect(r.stats![2]).toMatchObject({ isNumeric: true, key: 'death', value: 15 });
  });

  it('parses JSON as stats', () => {
    const r = parseMessageContent(
      'You wake up in a dungeon.\n---\n{"HP": 50, "MANA": 30, "ITEM": "sword"}',
    );
    expect(r.mainContent).toBe('You wake up in a dungeon.');
    expect(r.stats).toHaveLength(3);
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.stats![0]).toMatchObject({ isNumeric: true, key: 'hp', value: 50 });
    expect(r.stats![1]).toMatchObject({ isNumeric: true, key: 'mana', value: 30 });
    expect(r.stats![2]).toMatchObject({ isNumeric: false, key: 'item', value: 'sword' });
  });

  it('returns text as notification when not key:value or list', () => {
    const r = parseMessageContent('Level up!\n---\nПоздравляем! Ваш уровень повышен до 5!');
    expect(r.mainContent).toBe('Level up!');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.notification).toBe('Поздравляем! Ваш уровень повышен до 5!');
  });

  it('handles multi-line notification text', () => {
    const r = parseMessageContent(
      'Done.\n---\nПоздравляем!\nВаш уровень повышен до 5!\nНовый навык открыт!',
    );
    expect(r.mainContent).toBe('Done.');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.notification).toBe('Поздравляем!\nВаш уровень повышен до 5!\nНовый навык открыт!');
  });

  it('handles content without --- separator', () => {
    const content = 'The LLM says hello without any metadata.';
    const r = parseMessageContent(content);
    expect(r.mainContent).toBe(content);
    expect(r.stats).toBeNull();
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
  });

  it('handles empty content after ---', () => {
    const r = parseMessageContent('Some text.\n---\n');
    expect(r.mainContent).toBe('Some text.');
    expect(r.stats).toBeNull();
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
  });

  it('handles single line after --- as notification', () => {
    const r = parseMessageContent('Text.\n---\nJust one line of text');
    expect(r.mainContent).toBe('Text.');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.notification).toBe('Just one line of text');
  });

  it('handles = as separator in key:value', () => {
    const r = parseMessageContent('Stats.\n---\nHP = 100\nGold = 500');
    expect(r.mainContent).toBe('Stats.');
    expect(r.stats).toHaveLength(2);
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.stats![0]).toMatchObject({ key: 'hp', value: 100 });
    expect(r.stats![1]).toMatchObject({ key: 'gold', value: 500 });
  });

  it('handles multi-word keys', () => {
    const r = parseMessageContent('Test.\n---\nMax HP: 150\nSpell Power: 42');
    expect(r.mainContent).toBe('Test.');
    expect(r.stats).toHaveLength(2);
    expect(r.notification).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.stats![0]).toMatchObject({ key: 'max hp', value: 150 });
    expect(r.stats![1]).toMatchObject({ key: 'spell power', value: 42 });
  });

  // ── Actions (bullet list) ──

  it('parses hyphen bullet list as actions', () => {
    const r = parseMessageContent('Choose an action.\n---\n- Attack\n- Defend\n- Use magic');
    expect(r.mainContent).toBe('Choose an action.');
    expect(r.stats).toBeNull();
    expect(r.notification).toBeNull();
    expect(r.actions).toEqual(['Attack', 'Defend', 'Use magic']);
  });

  it('parses asterisk bullet list as actions', () => {
    const r = parseMessageContent('Pick one.\n---\n* Go left\n* Go right\n* Stay');
    expect(r.mainContent).toBe('Pick one.');
    expect(r.actions).toEqual(['Go left', 'Go right', 'Stay']);
  });

  it('parses numbered list as actions', () => {
    const r = parseMessageContent('Options:\n---\n1. Run away\n2. Fight\n3. Talk');
    expect(r.mainContent).toBe('Options:');
    expect(r.actions).toEqual(['Run away', 'Fight', 'Talk']);
  });

  it('treats mixed content (not all bullets) as notification', () => {
    const r = parseMessageContent('Info.\n---\nSome text\n- Not a bullet\n- Also not');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.notification).toBeTruthy();
  });

  // ── Structural --- separator (Task 2) ──
  //
  // NOTE: a setext heading underline like `Heading\n---\nBody`
  // is structurally indistinguishable from the legacy
  // single-newline separator `Body.\n---\nHP: 10`. We chose
  // backward compatibility with existing chat history — if a
  // bot emits `\n---\n` mid-content, we treat it as a separator.
  // For mid-content separators, prefer the new blank-line form
  // (`\n\n---\n`) when emitting new content.

  it('treats --- with blank lines around it as separator (new format)', () => {
    const r = parseMessageContent('Body paragraph.\n\n---\n\nHP: 10');
    expect(r.mainContent).toBe('Body paragraph.');
    expect(r.stats).toHaveLength(1);
  });

  it('treats --- at very start of content as separator', () => {
    const r = parseMessageContent('---\nHP: 10');
    expect(r.mainContent).toBe('');
    expect(r.stats).toHaveLength(1);
  });

  it('treats --- at very end of content as separator (new format)', () => {
    const r = parseMessageContent('Body.\n\n---');
    expect(r.mainContent).toBe('Body.');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
    expect(r.notification).toBeNull();
  });

  it('still parses legacy single-newline --- separator (backward compat)', () => {
    // Existing chat history uses `\n---\n` without blank lines.
    // This must keep working.
    const r = parseMessageContent('Old message.\n---\nHP: 5');
    expect(r.mainContent).toBe('Old message.');
    expect(r.stats).toHaveLength(1);
  });

  // ── YAML branch (Task 3) ──

  it('parses YAML mapping as stats', () => {
    // YAML mapping { HP: 10, GOLD: 20000 } — emitted as a flow
    // mapping on a single line so YAML parses it as object.
    const meta = '{ HP: 10, GOLD: 20000 }';
    const r = parseMessageContent(`You find loot.\n\n---\n\n${meta}`);
    expect(r.stats).toHaveLength(2);
    expect(r.stats![0]).toMatchObject({ isNumeric: true, key: 'hp', value: 10 });
    expect(r.stats![1]).toMatchObject({ isNumeric: true, key: 'gold', value: 20000 });
  });

  it('parses YAML sequence as actions', () => {
    // YAML inline sequence [Attack, Defend, Cast spell]
    const meta = '[Attack, Defend, Cast spell]';
    const r = parseMessageContent(`Choose:\n\n---\n\n${meta}`);
    expect(r.actions).toEqual(['Attack', 'Defend', 'Cast spell']);
    expect(r.stats).toBeNull();
  });

  it('parses YAML scalar string as notification when nothing else matches', () => {
    // A bare string with no `:` parses as YAML scalar. We
    // intentionally FALL THROUGH to the existing chain in this
    // case so kv / bullet / plain-text still works — a yaml
    // scalar of "HP: 10" should not short-circuit the kv parser.
    const r = parseMessageContent('Done.\n\n---\n\njust a plain scalar');
    expect(r.notification).toBe('just a plain scalar');
  });

  it('falls back to JSON when YAML mapping is invalid', () => {
    // Pure JSON object — YAML's `load` returns the same value
    // here, but we want to make sure the JSON path also still
    // works (defense in depth).
    const r = parseMessageContent(
      'Body.\n\n---\n\n{"HP": 50, "MANA": 30}',
    );
    expect(r.stats).toHaveLength(2);
  });

  it('falls back to key:value lines when YAML returns a plain scalar', () => {
    // Unquoted "HP: 10\nGOLD: 5" — YAML parses this as the string
    // "HP: 10\nGOLD: 5". We FALL THROUGH to the kv parser.
    const r = parseMessageContent('Body.\n\n---\n\nHP: 10\nGOLD: 5');
    expect(r.stats).toHaveLength(2);
    expect(r.stats![0]).toMatchObject({ key: 'hp', value: 10 });
    expect(r.stats![1]).toMatchObject({ key: 'gold', value: 5 });
  });

  // ── Edge cases (Task 4) ──

  it('does not parse anything when no --- separator', () => {
    const r = parseMessageContent('HP: 10\nGOLD: 20');
    expect(r.mainContent).toBe('HP: 10\nGOLD: 20');
    expect(r.stats).toBeNull();
  });

  it('does not crash on malformed YAML, falls through gracefully', () => {
    // Unterminated flow mapping — js-yaml throws.
    const r = parseMessageContent('Body.\n\n---\n\n{ malformed: ');
    expect(r.mainContent).toBe('Body.');
    // Branch unspecified — could be kv / bullets / notification.
    // Just verify no crash and one of the three fields populated.
    expect(
      r.stats !== null || r.actions !== null || r.notification !== null,
    ).toBe(true);
  });

  it('YAML scalar empty/null falls through to kv chain', () => {
    // YAML `~` parses as null. Object.entries({}) yields nothing,
    // so the YAML branch returns entries=0 and falls through.
    const r = parseMessageContent('Body.\n\n---\n\n~\n');
    // Falls through to notification branch (since `~` trims to '').
    expect(r.mainContent).toBe('Body.');
  });

  // ── Trailing YAML `---` sentinel (LLM closes metadata) ──

  it('parses YAML mapping with trailing --- sentinel (new format)', () => {
    // LLM often closes the metadata block with `---` on its own
    // line. Without stripping, js-yaml throws
    // "expected a single document in the stream, but found more"
    // and the whole block falls into the notification fallback.
    const r = parseMessageContent(
      'Body.\n\n---\n\n{ HP: 10, GOLD: 20000 }\n\n---',
    );
    expect(r.mainContent).toBe('Body.');
    expect(r.stats).toHaveLength(2);
    expect(r.notification).toBeNull();
  });

  it('parses YAML mapping with trailing --- (no blank line)', () => {
    const r = parseMessageContent(
      'Body.\n\n---\n\n{ HP: 10, GOLD: 20000 }\n---',
    );
    expect(r.stats).toHaveLength(2);
    expect(r.notification).toBeNull();
  });

  it('preserves trailing content after --- as notification', () => {
    // If something follows the `---`, it is NOT a sentinel —
    // it's real text. The strip helper only removes a trailing
    // `---` that sits at the very end of the metadata block, so
    // any text after it stays put. The whole block then falls
    // through to the plain-text notification fallback (yaml
    // rejects `---` mid-stream as a document separator) — but
    // crucially the data is NOT dropped.
    const r = parseMessageContent(
      'Body.\n\n---\n\n{ HP: 10 }\n---\n\nmore body',
    );
    expect(r.notification).toBe('{ HP: 10 }\n---\n\nmore body');
    expect(r.stats).toBeNull();
  });

  it('parses YAML sequence with trailing --- sentinel', () => {
    const r = parseMessageContent(
      'Choose:\n\n---\n\n[Attack, Defend]\n---',
    );
    expect(r.actions).toEqual(['Attack', 'Defend']);
    expect(r.notification).toBeNull();
  });

  it('falls through cleanly when only --- remains after strip', () => {
    // Sentinel-only metadata → after strip we have empty
    // string → falls through to plain-text notification with
    // empty body. Caller can detect via notification === ''.
    const r = parseMessageContent('Body.\n\n---\n\n---\n');
    expect(r.mainContent).toBe('Body.');
    expect(r.stats).toBeNull();
    expect(r.actions).toBeNull();
  });
});
