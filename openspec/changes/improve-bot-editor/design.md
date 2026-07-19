## Context

The Bots library (`BotsPage.svelte`, 952 LOC) currently shows every bot
returned by `GET /api/bots` with no ordering, no filter, no search, and
no type awareness — only inline delete by id (`BotsPage.svelte:209`). The
bot editor (`BotEditPage.svelte`, 2162 LOC) and creator
(`BotCreatePage.svelte`, 521 LOC) render the same full field set regardless
of `bot_type`, even though the backend orchestrator already branches on
`bot_type`:

- `app/infrastructure/orchestration/preambles.py:24` defines three
  distinct default preambles per type.
- `app/infrastructure/orchestration/langgraph_orchestrator.py:362-666`
  applies `uploaded_files` only for `ASSISTANT` / `AGENT`, runs the
  repairer only for `RP`.

So the form's surface area exceeds what half the bot types actually use,
which creates a parity gap (creator is missing 5 RP-only fields the
editor already has) and an inconsistency between what users see and what
the orchestrator consumes.

Constraints (from `AGENTS.md` and `config.yaml`):

- Frontend-only change — no backend, no DTO, no migration, no Alembic.
- Svelte 5 runes (`$state`, `$derived`), hash-routing SPA, no SvelteKit.
- Atomic components in `src/lib/ui/*`; composite in `src/lib/*`. New
  primitives land in `src/lib/ui/` (no domain types).
- TDD mandatory (AGENTS.md §2) — test before implementation.
- Docker-only verification — `make docker-frontend-lint`,
  `make docker-frontend-test`, no host `npm run lint`.
- Mobile touch targets ≥ 44×44px (DESIGN.md §Do's and Don'ts,
  `MOBILE_PLAN.md` Phase 4.5).

## Goals / Non-Goals

**Goals:**
1. Add sort / type-filter / name-search to `BotsPage` without changing
   the `GET /api/bots` contract.
2. Make `BotEditPage` and `BotCreatePage` field set vary by `bot_type`,
   matching the orchestrator's actual consumption.
3. Add a confirm dialog on type-switch when hidden RP-only fields
   contain unsaved content.
4. Provide TDD-first Vitest coverage for derived stores (sort/filter/
   search) and the type-switch confirm flow.
5. Pass `mobile-touch-targets.spec.ts` after changes — chips and
   dropdowns ≥ 44×44px on 412×915 viewport.

**Non-Goals** (deferred — see proposal Non-goals):
- Backend pagination / cursor sort / server-side search.
- URL persistence of filter state (`?type=rp`).
- Bot version history viewer.
- Changing default `bot_type` for new bots.
- Bulk actions on the library page.

## Decisions

### D1 — Client-side filter over backend pagination

Sort / filter / search happen in the browser over the existing
`GET /api/bots` response. No new endpoint, no new repo method.

- **Why**: keeps the change scoped to frontend; avoids re-doing backend
  pagination work that the library doesn't need yet.
- **Alternative considered**: add `?sort=&type=&q=` query params to
  `GET /api/bots`. Deferred because (a) the data set is small enough for
  in-memory ops, (b) it requires repo signature changes that cascade
  into ports, services, tests — out of scope for "improve editor".
- **Trade-off acknowledged**: as the library grows past several hundred
  bots, in-memory ops will get visibly slow. We document this in
  `Risks / Trade-offs` below.

### D2 — Type-aware field visibility, not field-disabled

When `bot_type` is `ASSISTANT` or `AGENT`, RP-only fields are **removed
from the DOM**, not just disabled. The submit payload MUST NOT include
those fields either.

- **Why**: matches what the orchestrator actually reads
  (`langgraph_orchestrator.py` only consumes fields relevant per type);
  shrinks the user's cognitive load; removes a class of "I typed in a
  field that gets silently ignored" bugs.
- **Alternative considered**: render all fields with `disabled` for
  non-applicable types. Rejected because it contradicts the orchestrator
  contract — user thinks they configured something they didn't.
- **Edge case**: `dynamic_system_prompt` is consumed for all three
  types, so it stays visible. `world_state_prompt` is RP-specific, hide
  for the other two.

### D3 — Confirm dialog on type switch with unsaved content

When switching `bot_type` and any currently-hidden RP-only field is
non-empty, show a `<Modal>` confirming discard before applying.

- **Why**: prevents accidental loss of curated content (e.g. a long
  `mes_example` the user spent 10 minutes on).
- **Implementation**: detect non-empty before applying the new type,
  show confirm. Cancel restores old type; Confirm proceeds and
  explicitly clears the hidden fields from the local form state.

### D4 — Reuse existing primitives

Sort dropdown → `<Select>` (already used in `BotEditPage:514`).
Filter chips → `<Badge>` (active state via `bg-rp-accent`,
`text-rp-text-primary`).
Search input → `<Input>` with a clear button.
Confirm dialog → `<Modal>`.
Type-switch detection → pure helper function `hasHiddenRPContent(form)`.

- **Why**: AGENTS.md §5 bans reinventing components; DESIGN.md says
  "composite components are domain-aware, atomic components are not".
- **Trade-off**: chips might feel a bit small on mobile. We'll
  compensate with the existing chip-padding pattern from
  `Dashboard.svelte` / `BotEditPage.svelte`.

### D5 — Derived stores for filtered/sorted list

Use Svelte 5 `$derived` to compute `visibleBots` from
`$state.rawBots`, `$state.sortKey`, `$state.sortDir`,
`$state.activeTypes`, `$state.searchQuery`.

- **Why**: declarative, no manual subscriptions, no race conditions
  between sort/filter/search. Matches Svelte 5 idiom (AGENTS.md §5
  Frontend conventions).
- **Alternative considered**: a `writable` store with explicit setters.
  Rejected — `$derived` is simpler and plays well with component-local
  state.

## Layer-by-layer change

```
frontend/src/lib/pages/BotsPage.svelte       ← + sort dropdown, + filter chips, + search input, + derived store
frontend/src/lib/pages/BotEditPage.svelte    ← conditional render of fields by bot_type, + type-switch confirm
frontend/src/lib/pages/BotCreatePage.svelte  ← + missing RP fields for parity, + conditional render, + type-switch confirm
frontend/src/lib/i18n/                       ← + bot_library.* namespace, + bot_edit.confirm_type_switch.*
frontend/src/lib/__tests__/                  ← + botsBrowse.test.ts, + botEditorConditionalFields.test.ts, + botCreatePageParity.test.ts
```

No changes to: `app/`, `api/`, `tests/` (Python), `alembic/`,
`docker-compose*.yml`, `Dockerfile*`.

## Component tree (BotsPage additions)

```
BotsPage
├── BotsToolbar              [new, composite — domain-aware]
│   ├── SortSelect           [reuses ui/Select.svelte]
│   ├── TypeFilterChips      [composite — uses BOT_TYPES from api.ts + ui/Badge.svelte]
│   └── SearchInput          [composite — uses ui/Input.svelte + clear button]
├── BotsList                 [existing — derived visibleBots]
└── EmptyState / Loading     [existing — ui/Loading.svelte, error banner]
```

## Component tree (BotEditPage / BotCreatePage additions)

```
BotEditPage / BotCreatePage
└── FormSection              [new tiny helper — renders slot only when condition holds]
    ├── <when type === 'rp'>
    │   ├── AlternateGreetings editor (edit only)
    │   ├── MesExample editor   (edit only)
    │   ├── WorldStatePrompt    (edit only)
    │   └── FirstMessage / Scenario (both)
    └── <when type === 'assistant' | 'agent'>
        └── SystemPromptBlock (extended)
```

`FormSection` is a tiny Svelte snippet wrapper, not a heavy component.
Both pages adopt it for consistency.

## i18n keys (new)

Namespace `bot_library.*`:
- `bot_library.sort_label`, `bot_library.sort_name_asc`,
  `bot_library.sort_name_desc`, `bot_library.sort_id_asc`,
  `bot_library.sort_id_desc`, `bot_library.sort_threads_desc`
- `bot_library.filter_types_label`, `bot_library.filter_clear_all`
- `bot_library.search_placeholder`, `bot_library.empty_state`
- `bot_library.error_fetch`, `bot_library.retry`
- `bot_library.results_count` (with `{count}` placeholder)

Namespace `bot_edit.confirm_type_switch.*`:
- `bot_edit.confirm_type_switch.title`
- `bot_edit.confirm_type_switch.body`
- `bot_edit.confirm_type_switch.confirm`
- `bot_edit.confirm_type_switch.cancel`

All keys must exist in both `en` and `ru` (see `i18n.ts`).

## DESIGN.md / MOBILE_PLAN.md citations

- **§Colors / tokens** — chip active state uses `bg-rp-accent`,
  inactive uses `bg-rp-surface`. No hardcoded hex. See DESIGN.md §Colors.
- **§Hover states** — chips: opacity 0.8 on hover, NO
  `transform: scale()` or `translateY()`. Border-radius fixed at the
  `<Badge>` default — no hover flip.
- **§Tooltip** — filter chip overflow description uses `<Tooltip>`,
  NOT `<element title="...">` (banned per DESIGN.md).
- **MOBILE_PLAN.md Phase 4.5** — touch targets ≥ 44×44px on phones.
  Sort dropdown trigger and each filter chip MUST measure ≥ 44×44px on
  412×915 viewport. `mobile-touch-targets.spec.ts` is the gate.
- **MOBILE_PLAN.md Phase 5** — chip overflow on narrow viewports MUST
  scroll horizontally with a fade mask
  (`mask-image: linear-gradient(...)`), matching `Dashboard.svelte`
  filter pills pattern.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Client-side filter slow past ~500 bots | Document in `docs/PLAN.md` backlog; revisit D1 then. Add a Vitest perf budget assertion if simple to write. |
| Type-switch confirm dialog could be annoying for power users | Future: "Don't ask again" pref stored in localStorage. Out of scope v1. |
| `dynamic_system_prompt` per-message rule (AGENTS.md §2 critical note) is unrelated to this change | This change does NOT touch `_build_all_messages` or `_node_user_input`. Confirmed by grep across both functions. |
| BotEditPage is 2162 LOC; risk of merge conflicts in long file | Refactor into `<FormSection>` snippets in the SAME commit as the conditional render — no half-applied refactor left in main. |
| Multi-page parity drift: BotsPage sort UI must match Dashboard filter chips | Reuse `Badge` and chip-padding from existing patterns; reuse `Dashboard.svelte` filter mask for mobile. |
| Vitest jsdom doesn't model `localeCompare` exactly the same as Chrome | Use `Intl.Collator(undefined, { sensitivity: 'base' })` — same in jsdom and Chrome; pin via unit test. |

## Migration Plan

No DB migration. No backend deploy. Frontend ships in a single PR.

**Rollback**: revert the PR. No data is altered, so a rollback is a pure
UI restoration.

**Feature flag / staged rollout**: not used — change is additive, no
breaking contract.

## Open Questions

1. **Sort by `thread_count`** — `thread_count` is not currently on
   `BotResponse` (only `bot_type` and `description`). Need to confirm
   if `BotResponse` exposes thread counts already (likely yes via a
   `with_count` endpoint variant). If not, sort by `thread_count`
   becomes a follow-up and we ship with `name` / `created_at` first.
2. **`<Toggle>` for filter chips vs `<Badge>`** — `<Badge>` is the
   pattern used elsewhere; `<Toggle>` is for binary on/off. Decision:
   `<Badge>` for type filter, but a wrapping `<button>` for keyboard
   accessibility. Confirm in code review.
3. **Should the search input debounce?** — at ~hundreds of bots in
   memory, no. Add only if profiling shows jank on keypress.

These are tracked in `tasks.md` and can be resolved during implementation.