/** Tests for ``src/lib/botEditor.ts``.

Pins the contract of the type-aware conditional field helpers used by
both ``BotEditPage.svelte`` and ``BotCreatePage.svelte``. The helpers
are pure functions so we can test them in isolation, without standing
up the Svelte runtime or hitting the backend.

Background (see ``openspec/changes/improve-bot-editor/specs/bot-editor-type-aware/spec.md``):
- ``bot_type`` is one of RP / ASSISTANT / AGENT (see ``BotType`` enum in ``api.ts``).
- RP shows the full character-card field set; ASSISTANT / AGENT hide
  the RP-only fields (alternate_greetings, first_message, scenario,
  mes_example, world_state_prompt). dynamic_system_prompt is visible
  for all types because the orchestrator consumes it everywhere
  (``langgraph_orchestrator.py``).
- When the user switches type away from RP while any RP-only field has
  content, ``hasHiddenRPContent`` returns true so the UI can prompt
  before discarding the work.
*/

import { describe, expect, it } from 'vitest';

import {
  hasHiddenRPContent,
  isRPOnlyFieldKey,
  type RPEditorFormState,
} from '../botEditor';

function makeForm(over: Partial<RPEditorFormState> = {}): RPEditorFormState {
  return {
    alternate_greetings: [],
    dynamic_system_prompt: '',
    first_message: '',
    mes_example: '',
    world_state_prompt: '',
    ...over,
  };
}

describe('hasHiddenRPContent', () => {
  it('returns false on a fully empty form (nothing to lose)', () => {
    expect(hasHiddenRPContent('rp', makeForm())).toBe(false);
    expect(hasHiddenRPContent('assistant', makeForm())).toBe(false);
    expect(hasHiddenRPContent('agent', makeForm())).toBe(false);
  });

  it('returns false on RP regardless of content (no fields are hidden)', () => {
    // When staying on RP, every field is visible — the helper
    // exists to gate the type-switch confirmation, not to flag
    // form validity.
    expect(
      hasHiddenRPContent(
        'rp',
        makeForm({
          alternate_greetings: ['Hello!'],
          first_message: 'Hi there',
          mes_example: '<START>\n{{user}}: hi\n{{char}}: hey\n<END>',
          world_state_prompt: 'You are in a tavern.',
        }),
      ),
    ).toBe(false);
  });

  it('returns true on ASSISTANT when first_message is non-empty', () => {
    expect(
      hasHiddenRPContent('assistant', makeForm({ first_message: 'Hi there' })),
    ).toBe(true);
  });

  it('returns true on AGENT when first_message is non-empty', () => {
    expect(
      hasHiddenRPContent('agent', makeForm({ first_message: 'Hi there' })),
    ).toBe(true);
  });

  it('returns true when alternate_greetings has any non-empty entry', () => {
    // Whitespace-only greetings don't count — a user who typed only
    // spaces hasn't actually committed to that greeting yet.
    expect(
      hasHiddenRPContent('assistant', makeForm({ alternate_greetings: ['real greeting'] })),
    ).toBe(true);

    expect(
      hasHiddenRPContent(
        'assistant',
        makeForm({ alternate_greetings: ['   ', '\t\n'] }),
      ),
    ).toBe(false);
  });

  it('returns true when mes_example has content (raw V1/V2/V3 text)', () => {
    expect(
      hasHiddenRPContent(
        'assistant',
        makeForm({ mes_example: '<START>\n{{user}}: hi\n{{char}}: hey\n<END>' }),
      ),
    ).toBe(true);
  });

  it('returns true when world_state_prompt has content', () => {
    expect(
      hasHiddenRPContent('agent', makeForm({ world_state_prompt: 'You are in a tavern.' })),
    ).toBe(true);
  });

  it('treats dynamic_system_prompt as NOT RP-only (consumed for all types)', () => {
    // The orchestrator reads dynamic_system_prompt for every bot_type,
    // so even when switching away from RP, this field stays visible.
    // The helper must NOT treat it as a hidden-field-loss risk.
    expect(
      hasHiddenRPContent('assistant', makeForm({ dynamic_system_prompt: 'long system prompt' })),
    ).toBe(false);
    expect(
      hasHiddenRPContent('agent', makeForm({ dynamic_system_prompt: 'long system prompt' })),
    ).toBe(false);
  });

  it('combines multiple hidden fields via OR (any non-empty triggers)', () => {
    expect(
      hasHiddenRPContent(
        'assistant',
        makeForm({
          alternate_greetings: [],
          first_message: '',
          mes_example: '',
          world_state_prompt: 'one is enough',
        }),
      ),
    ).toBe(true);

    expect(
      hasHiddenRPContent(
        'assistant',
        makeForm({
          alternate_greetings: ['a'],
          first_message: 'b',
          mes_example: 'c',
          world_state_prompt: 'd',
        }),
      ),
    ).toBe(true);
  });

  it('treats zero-length strings as empty', () => {
    // Sanity guard: empty strings (not just whitespace) must not
    // trigger the prompt — they carry no information to lose.
    expect(
      hasHiddenRPContent('assistant', makeForm({ first_message: '', mes_example: '', world_state_prompt: '' })),
    ).toBe(false);
  });
});

describe('isRPOnlyFieldKey', () => {
  // Pure-constant catalog of which form-state keys are RP-only.
  // Used by the editor to decide which fields to conditionally render
  // AND which fields to omit from the submit payload when not RP.
  it('identifies the five RP-only keys', () => {
    expect(isRPOnlyFieldKey('alternate_greetings')).toBe(true);
    expect(isRPOnlyFieldKey('first_message')).toBe(true);
    expect(isRPOnlyFieldKey('mes_example')).toBe(true);
    expect(isRPOnlyFieldKey('scenario')).toBe(true);
    expect(isRPOnlyFieldKey('world_state_prompt')).toBe(true);
  });

  it('rejects the all-types-visible keys', () => {
    expect(isRPOnlyFieldKey('dynamic_system_prompt')).toBe(false);
    expect(isRPOnlyFieldKey('name')).toBe(false);
    expect(isRPOnlyFieldKey('personality')).toBe(false);
    expect(isRPOnlyFieldKey('description')).toBe(false);
  });

  it('rejects unknown keys defensively', () => {
    // If a future contributor adds a new form-state key and forgets
    // to register it in the catalog, isRPOnlyFieldKey returns false
    // (safe default — field stays visible rather than silently hidden).
    // The cast is intentional: the type system doesn't know these
    // keys exist, and the test exists specifically to lock down the
    // runtime behaviour for unknown input.
    const unknownKey: string = 'not_in_catalog';
    expect(isRPOnlyFieldKey(unknownKey)).toBe(false);
    expect(isRPOnlyFieldKey('avatar_path')).toBe(false);
  });
});