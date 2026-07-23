# bot-editor-type-aware Specification

## Purpose
TBD - created by archiving change improve-bot-editor. Update Purpose after archive.
## Requirements
### Requirement: Field set varies by bot_type

The bot editor (`BotEditPage`) and the bot creator (`BotCreatePage`) MUST
display a field set whose composition depends on the selected `bot_type`.
The contract MUST match what the orchestrator actually consumes:
- `RP`: all character-card fields are visible and editable.
- `ASSISTANT` and `AGENT`: RP-specific RP-only fields are hidden.

#### Scenario: RP bot shows full field set
- **WHEN** `bot_type` is `rp`
- **THEN** the editor renders `personality`, `first_message`,
  `alternate_greetings`, `scenario`, `description`, `mes_example`,
  `dynamic_system_prompt`, `world_state_prompt`, and avatar upload
- **AND** the Round-trip scenario below MUST pass: save the bot with
  non-empty values in each field, reload it via `GET /api/bots/{id}`, and
  assert every field round-trips. This covers the silent-DB-drop class
  of bugs flagged in AGENTS.md §2.

#### Scenario: ASSISTANT bot hides RP-only fields
- **WHEN** `bot_type` is `assistant`
- **THEN** the editor renders `personality`, `description`, and an extended
  `system_prompt`-style block
- **AND** `first_message`, `alternate_greetings`, `scenario`, `mes_example`,
  `world_state_prompt` are hidden
- **AND** `dynamic_system_prompt` MAY remain visible (used by orchestrator
  for all types per `langgraph_orchestrator.py`)

#### Scenario: AGENT bot hides RP-only fields
- **WHEN** `bot_type` is `agent`
- **THEN** the editor renders the same set as ASSISTANT
- **AND** `uploaded_files` handling differs at the orchestrator layer
  (`langgraph_orchestrator.py:365, 666`) — this difference is consumed
  backend-side and does not require editor changes

### Requirement: Type switch with unsaved changes

The bot editor MUST prevent accidental data loss when the user switches
`bot_type` while RP-only fields contain unsaved content.

#### Scenario: Switch type with empty RP-only fields
- **WHEN** the user changes `bot_type` from `rp` to `assistant`
- **AND** all hidden RP-only fields are empty
- **THEN** the field set updates immediately with no confirmation

#### Scenario: Switch type with non-empty RP-only fields
- **WHEN** the user changes `bot_type` from `rp` to `assistant`
- **AND** at least one of `first_message`, `alternate_greetings`,
  `scenario`, `mes_example`, `world_state_prompt` is non-empty
- **THEN** a confirm dialog appears with text describing which fields will
  be hidden
- **AND** confirming hides the fields and discards unsaved changes
- **AND** cancelling restores the previous `bot_type` value

#### Scenario: Same-type change is a no-op
- **WHEN** the user selects the same `bot_type` they already have
- **THEN** no confirmation dialog appears and the field set is unchanged

### Requirement: Create-page parity with edit-page

The bot creator (`BotCreatePage`) MUST apply the same type-aware field
visibility rules as the bot editor. Today `BotCreatePage.svelte` lacks
`mes_example`, `alternate_greetings`, `dynamic_system_prompt`,
`world_state_prompt` entirely; this is a parity gap flagged during proposal.

#### Scenario: Create RP bot
- **WHEN** the user picks `bot_type=rp` and submits `BotCreatePage`
- **THEN** the created bot round-trips via `GET /api/bots` with all
  RP-only fields populated exactly as entered (round-trip per AGENTS.md §2)

#### Scenario: Create ASSISTANT bot
- **WHEN** the user picks `bot_type=assistant` and submits `BotCreatePage`
- **THEN** the created bot round-trips with `bot_type="assistant"` and
  only the fields visible for that type are persisted

### Requirement: Form validation matches visible fields

The bot editor and creator MUST only validate fields that are currently
visible. Hidden fields MUST NOT block submission even if their underlying
values are empty.

#### Scenario: Submit RP bot with empty alternate_greetings
- **WHEN** the user submits an RP bot with `alternate_greetings == []`
- **THEN** the request succeeds (empty list is valid for RP)

#### Scenario: Submit ASSISTANT bot without alternate_greetings field
- **WHEN** the user submits an ASSISTANT bot
- **THEN** the request payload MUST NOT include `alternate_greetings`
  (or any RP-only hidden field) — backend treats missing as default empty

