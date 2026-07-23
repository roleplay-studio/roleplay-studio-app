## ADDED Requirements

### Requirement: Sort bots by selectable field

The Bots library page MUST allow the user to sort the displayed list by
`name`, `created_at`, or `thread_count`. Each sortable dimension MUST be
orderable in both ascending and descending directions.

#### Scenario: Default sort on first load
- **WHEN** the user opens the Bots library page for the first time in a session
- **THEN** the list is sorted by `created_at` descending (newest first)

#### Scenario: User picks a different sort dimension
- **WHEN** the user selects "Name (A→Z)" from the sort dropdown
- **THEN** the list is sorted by `name` ascending using locale-aware comparison

#### Scenario: Sort applies after filter
- **WHEN** the user has an active filter (for example `bot_type=rp`) and
  changes the sort order
- **THEN** the filtered subset is re-sorted by the new dimension

### Requirement: Filter bots by type

The Bots library page MUST allow the user to filter the displayed list by
one or more `BotType` values (RP / ASSISTANT / AGENT). The filter MUST be
multi-select with a "Clear all" affordance.

#### Scenario: No filter active
- **WHEN** the user has not selected any filter chip
- **THEN** bots of every `bot_type` are visible

#### Scenario: Single-type filter
- **WHEN** the user activates the "RP" filter chip
- **THEN** only bots with `bot_type == "rp"` are visible
- **AND** the chip displays an active visual state (per AGENTS.md §5:
  active `bg-rp-*` background, no `transform: scale()` on hover)

#### Scenario: Multi-type filter
- **WHEN** the user activates "RP" and "ASSISTANT" chips
- **THEN** bots matching either type are visible (logical OR)
- **AND** the count of visible bots updates in the result summary

#### Scenario: Clear filter
- **WHEN** the user clicks "Clear all"
- **THEN** all chips deactivate
- **AND** the full unfiltered list is restored

### Requirement: Search bots by name

The Bots library page MUST allow the user to filter the displayed list by
a free-text substring search against `name`. Search MUST be
case-insensitive and MUST combine with the type filter (logical AND).

#### Scenario: Empty search
- **WHEN** the search input is empty
- **THEN** search has no effect on the displayed list

#### Scenario: Matching substring
- **WHEN** the user types "lor" into the search input
- **THEN** only bots whose `name` contains "lor" (case-insensitive) are visible
- **AND** type filter and search combine via logical AND

#### Scenario: No matches
- **WHEN** the user types a query that matches no bot
- **THEN** an empty-state message is rendered in place of the list

### Requirement: Empty and loading states

The Bots library page MUST render appropriate states for empty, loading,
and error conditions, independent of the active sort/filter/search.

#### Scenario: Initial load
- **WHEN** the page is mounted and the bot fetch has not yet resolved
- **THEN** a loading indicator is shown (no filter UI is interactive)

#### Scenario: Fetch error
- **WHEN** `GET /api/bots` returns a non-2xx response
- **THEN** an inline error message is rendered with a retry button
- **AND** sort/filter/search controls remain visible but disabled