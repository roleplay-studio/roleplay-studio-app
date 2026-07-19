## Why

The Bots library page (`BotsPage.svelte`) currently renders every bot with no
ordering, no type filter, and no search — only inline delete by id
(`BotsPage.svelte:209`). As the library grows past a handful of bots this
becomes unmanageable. Separately, `BotEditPage.svelte` (2162 lines) shows the
same full field set regardless of `bot_type`, even though backend behaviour
already differs per type (`preambles.py`, `langgraph_orchestrator.py:362-666`):
for `RP` the repairer runs; for `ASSISTANT`/`AGENT` `uploaded_files` is
processed. The form does not reflect that contract.

This change adds sort + filter + search to the Bots library, and makes the
bot editor's input set type-aware so the form matches what the orchestrator
actually consumes.

## What Changes

- **Bots library (`BotsPage.svelte`)**: add sort dropdown (name asc/desc,
  created_at asc/desc, threads_count desc), filter chips for `BotType`
  (RP / ASSISTANT / AGENT) with multi-select + clear, and a free-text search
  by name. State is per-session.
- **Bot editor (`BotEditPage.svelte`, `BotCreatePage.svelte`)**: hide
  `mes_example`, `alternate_greetings`, `scenario`, `first_message`,
  `world_state_prompt` when `bot_type` is `ASSISTANT` or `AGENT`; show
  only `personality` + a richer `system_prompt`-style block. Keep all
  fields editable when `bot_type` is `RP`. Switching `bot_type` while
  editing a non-empty field shows a confirm dialog before discarding.
- **Backend**: no DTO change, no new column. `bot_type` already round-trips
  in `BotResponse`. Sort/filter/search are client-side over the existing
  `GET /api/bots` response — single fetch, in-memory filter. Keeps the
  surface area minimal and avoids backend pagination work.

## Capabilities

### New Capabilities
- `bot-library-browse`: client-side sort, filter, and search over the bots
  list returned by `GET /api/bots`.
- `bot-editor-type-aware`: form field visibility and required-field set
  varies by `bot_type`; switching type with unsaved changes prompts user.

### Modified Capabilities
- *(none — no spec-level requirement changes; existing behaviour is preserved
  for all `bot_type` values, only the editor UI narrows.)*

## Impact

**Affected layers**: `frontend` (BotsPage, BotEditPage, BotCreatePage,
src/lib/api.ts — types unchanged), `i18n` (new keys under `bot_library.*`
and `bot_edit.*` in en/ru), `tests` (Vitest for derived stores +
component behaviour).

**3-step change risk**: NONE — no new column, no DTO field, no migration.
DB layer untouched.

**Parallel-prompt-path risk**: NONE — does not touch
`_build_all_messages` / `_node_user_input` / `regenerate_state`.

**Non-goals** (deferred to future changes): backend pagination,
URL-persistent filter state, bot version history UI, default-bot_type
change, bulk actions (multi-select / bulk delete / bulk export).

**Verification plan** lives in `design.md` and `tasks.md` (Docker targets,
OCR step, mobile touch-target audit, manual smoke per AGENTS.md §4 / §4a /
§4b).