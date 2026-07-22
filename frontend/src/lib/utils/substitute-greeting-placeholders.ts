/**
 * Substitute ``{{user}}`` template tokens in bot greeting text with
 * the current persona name. Mirrors the backend's
 * ``_variable_replace`` (app/application/services/chat.py) so the
 * UI shows the same text the LLM will see.
 *
 * The backend's ``_variable_replace`` runs at prompt-assembly time
 * (so the LLM always gets the substituted form) and at
 * ``stream_save_first_message`` time (so the persisted greeting
 * row in the DB is also substituted). What's missing is the
 * runtime UI display in the greeting switcher — those are
 * rendered directly from ``bot.first_message`` /
 * ``bot.alternate_greetings`` (which the backend serves verbatim,
 * with the placeholder intact) and shown to the user in the
 * chat panel.
 *
 * Without this substitution the user sees literal ``{{user}}``
 * in the chat panel even when the corresponding DB row has
 * ``Alice`` — a confusing inconsistency. The fix: substitute at
 * the same boundary the backend does, so the UI and the
 * persisted state match.
 *
 * ``personaName`` of ``null`` / ``""`` is a no-op (mirrors the
 * backend semantics — the orchestrator will substitute on the
 * first turn if no persona is selected, and a later persona
 * change can still re-substitute without the old name being
 * baked in).
 */
export function substituteGreetingPlaceholders(
  text: string,
  personaName: null | string,
): string {
  if (!personaName) {
    return text;
  }
  return text.replace(/\{\{user\}\}/g, personaName);
}
