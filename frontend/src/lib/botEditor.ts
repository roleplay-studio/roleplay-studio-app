/**
 * Pure helpers for the type-aware Bot editor (introduced by
 * ``improve-bot-editor``). These functions decouple the contract of
 * "which fields are RP-only" and "is there content the user would
 * lose" from the Svelte components, so the logic is unit-testable
 * in plain Vitest without standing up the editor UI.
 *
 * Background (see ``specs/bot-editor-type-aware/spec.md``):
 * - ``bot_type`` is one of RP / ASSISTANT / AGENT (see ``BotType``
 *   in ``api.ts``).
 * - RP shows the full character-card field set; ASSISTANT / AGENT
 *   hide the RP-only fields. ``dynamic_system_prompt`` is visible
 *   for all types because the orchestrator consumes it everywhere
 *   (``langgraph_orchestrator.py``).
 * - When switching type away from RP while any RP-only field has
 *   unsaved content, the UI must prompt before discarding the work.
 */

import type { BotType } from './api';

/**
 * Subset of the editor form state that ``hasHiddenRPContent`` reads.
 * Kept narrow so the helper stays trivially unit-testable without
 * pulling in the full ``Bot`` or ``BotCreateCommand`` shapes.
 */
export interface RPEditorFormState {
  /** RP-only — V1/V2/V3 character-card alternate greetings. */
  alternate_greetings: string[];
  /** All-types — orchestrator-consumed floating system prompt. */
  dynamic_system_prompt: string;
  /** RP-only — opening message. */
  first_message: string;
  /** RP-only — V1/V2/V3 character-card few-shot dialogue examples. */
  mes_example: string;
  /** RP-only — background state-update prompt. */
  world_state_prompt: string;
}

/**
 * Catalog of form-state keys that are hidden when ``bot_type`` is
 * anything other than ``rp``. Keep this list in sync with
 * ``specs/bot-editor-type-aware/spec.md`` §Requirement: Field set
 * varies by bot_type.
 *
 * IMPORTANT: ``dynamic_system_prompt`` is intentionally NOT in this
 * set — the orchestrator reads it for all bot types
 * (``langgraph_orchestrator.py`` builds the system message from it
 * regardless of type), so hiding it for ASSISTANT/AGENT would be a
 * silent data-loss bug.
 */
const RP_ONLY_FIELD_KEYS = new Set<string>([
  'alternate_greetings',
  'first_message',
  'mes_example',
  'scenario',
  'world_state_prompt',
]);

/**
 * Predicate: does the form contain content in any RP-only field
 * that would be hidden if the user switched ``bot_type`` away from
 * ``rp``? Empty strings and whitespace-only array entries do NOT
 * count — the user hasn't committed to that content yet, so
 * discarding it costs nothing.
 *
 * Returns ``false`` when ``currentType`` is ``rp`` itself: in that
 * case no field is being hidden, so there is nothing to confirm.
 */
export function hasHiddenRPContent(
  currentType: BotType,
  form: RPEditorFormState,
): boolean {
  if (currentType === 'rp') return false;

  if (form.first_message.trim() !== '') return true;
  if (form.world_state_prompt.trim() !== '') return true;
  if (form.mes_example.trim() !== '') return true;
  if (form.alternate_greetings.some((g) => g.trim() !== '')) return true;

  return false;
}

/**
 * Predicate: does the given form-state key belong to the RP-only
 * subset? ``false`` is the safe default — a future contributor who
 * adds a new form-state key without registering it here gets a field
 * that stays visible for all types, which is recoverable in QA.
 * ``true`` for an unregistered key would silently hide user content.
 */
export function isRPOnlyFieldKey(key: string): boolean {
  return RP_ONLY_FIELD_KEYS.has(key);
}