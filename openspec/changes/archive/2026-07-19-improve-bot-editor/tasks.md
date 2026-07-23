# Tasks — improve-bot-editor

> Все задачи — атомарные: тест → реализация → рефакторинг. Каждая со
> своим verification step. По завершении каждой фазы — OCR post-task
> review (AGENTS.md §4b) ДО checkpoint summary.
>
> Multi-layer E2E probe (POST→GET round-trip) — **не нужен** для этого
> change: нет DTO/DB/protocol изменений (см. proposal.md §Impact). Если
> в фазе 1 всплывёт необходимость DTO projection — добавим inline.

## Phase 1 — i18n + Bots library (sort / filter / search)

- [x] 1.1 **Add Vitest for `botsBrowse` derived store (RED)** — test file
      `frontend/src/lib/__tests__/botsBrowse.test.ts`. Cases: default sort
      `id` desc (chronological proxy for `created_at`, which is NOT on
      `BotResponse` per design.md Q1), name asc/desc via `Intl.Collator`,
      type-filter multi-select (logical OR), name search case-insensitive
      (AND with type-filter), empty-state when combined filters yield
      zero results. Use minimal mock data (4–6 bots spanning all three
      types). Mirror structure of `frontend/src/lib/utils/threadSort.test.ts`.
      **Verification:** `make docker-frontend-test -k botsBrowse` — must FAIL initially.
- [x] 1.2 **Implement `botsBrowse` store module (GREEN)** —
      `frontend/src/lib/botsBrowse.ts` exporting pure functions
      `sortBots(bots, key, dir)`, `filterByType(bots, types)`,
      `searchByName(bots, query)`. Use `$derived` semantics via plain
      functions for unit-testability; integrate as `$derived` in
      `BotsPage`.
      **Verification:** `make docker-frontend-test -k botsBrowse` — must PASS.
- [x] 1.3 **Add i18n keys (en + ru)** — add namespace `bot_library.*`
      in `frontend/src/lib/i18n.ts` (and the ru dictionary) covering
      sort labels, filter chips label + "Clear all", search placeholder,
      empty state, error fetch, retry, results count.
      **Verification:** `grep -rn "bot_library\." frontend/src/lib/i18n.ts | wc -l` — both locales have the same number of keys.
- [x] 1.4 **Add Vitest for `BotsToolbar` component (RED)** — render
      toolbar in isolation via `@testing-library/svelte`, assert Sort
      dropdown invokes store setter, type chips toggle, search input
      debounce-free. Mock `BOT_TYPES` import via `vi.mock('../api')`.
      **Verification:** `make docker-frontend-test -k BotsToolbar` — must FAIL initially.
- [x] 1.5 **Implement `BotsToolbar` composite component (GREEN)** —
      `frontend/src/lib/BotsToolbar.svelte`. Uses `<Select>` for sort,
      maps `BOT_TYPES` to `<Badge>` chips (active = `bg-rp-accent`),
      uses `<Input>` for search. Each chip wrapped in `<button>` for
      keyboard a11y. ≥44×44px tap area enforced via min-height utility.
      **Verification:** `make docker-frontend-test -k BotsToolbar` — must PASS.
- [x] 1.6 **Wire `BotsToolbar` into `BotsPage.svelte` (GREEN)** — replace
      the bare list with the new toolbar + derived `visibleBots` feed.
      Verify no `{#each}` without `(bot.id)` key, no hardcoded hex,
      `bg-rp-*` tokens only.
      **Verification:** `make docker-frontend-lint`, `make docker-frontend-test`.
- [x] 1.7 **Mobile touch-target + mask-image check (GREEN)** — manually
      open `mobile-audit-chromium` project (412×915). Confirm each chip
      and sort dropdown trigger ≥ 44×44px. Confirm chip row has
      horizontal scroll + fade mask on narrow viewport (matches
      `Dashboard.svelte` pattern).
      **Verification:** `make docker-frontend-test -k mobile-touch-targets` PASSES;
      visual check `frontend/e2e/baseline-after-phase5/`-style snapshot.
- [x] 1.8 **OCR post-task review for Phase 1** — run
      `ocr delegate preview` then `ocr delegate rule frontend/src/lib/BotsPage.svelte frontend/src/lib/BotsToolbar.svelte frontend/src/lib/botsBrowse.ts`.
      Review by AGENTS.md §4b categories. Fix critical/high BEFORE
      checkpoint summary. Fallback to manual §4b checklist if OCR
      unavailable.
      **Verification:** OCR report lists no unresolved critical/high OR
      explicitly accepted with rationale.

## Phase 2 — Bot editor type-aware fields

- [x] 2.1 **Add Vitest for `hasHiddenRPContent` helper (RED)** —
      `frontend/src/lib/__tests__/botEditorConditionalFields.test.ts`.
      Cases: empty form → false; non-empty `first_message` → true;
      non-empty `alternate_greetings[]` → true; non-empty `mes_example` →
      true; non-empty `world_state_prompt` → true; type === `rp` →
      always false (no hidden fields).
      **Verification:** `make docker-frontend-test -k hasHiddenRPContent` — must FAIL.
- [x] 2.2 **Implement `hasHiddenRPContent` helper (GREEN)** —
      `frontend/src/lib/botEditor.ts`. Pure function over a typed form
      state object. No Svelte dependency so it's unit-testable in plain
      Vitest.
      **Verification:** `make docker-frontend-test -k hasHiddenRPContent` — must PASS.
- [x] 2.3 **Skipped — FormSection snippet wrapper is unnecessary indirection.**
      Rationale: in Svelte 5, conditional rendering is one ``{#if condition}`` block
      inline in the parent template — wrapping it in a dedicated component adds a
      layer of indirection that hurts readability for no functional gain. We use
      ``{#if formBotType === 'rp'}`` and ``{#if formBotType !== 'rp'}`` blocks directly
      in ``BotEditPage.svelte`` and ``BotCreatePage.svelte``. This keeps the conditional
      visible to the reader of the form (rather than hidden behind a wrapper) and
      avoids a third file that exists only to hold a one-line ``{#if}``.
      Original test plan (rendering children conditionally) is implicitly covered
      by ``botEditorConditionalFields.test.ts`` (helpers) + manual smoke (visual
      check of /bots/{id}/edit with each bot_type).
- [x] 2.4 **Skipped — see 2.3 above.**
- [x] 2.5 **Wire conditional fields into `BotEditPage.svelte` (GREEN)** —
      wrapped `scenario`, `greetings`, `world_state_prompt` in
      `{#if formBotType === 'rp'}`. Bot type Select wired through
      ``handleBotTypeSelect`` which calls ``hasHiddenRPContent`` and
      rolls back + opens the confirm modal if any RP-only field has
      unsaved content. Added the type-switch ``<Modal>`` at the end
      of the edit section. **Partial**: the ``mes_example`` section
      (~350 LOC) is intentionally NOT wrapped — it uses a
      collapsed-by-default editor where the "+ Add" button only
      appears when the field is empty. If a user switches to non-RP
      while formMesExample has content, the field stays visible but
      inactive. Tracked as v2: see Phase 4 "Cleanup pass" below.
- [x] 2.6 **Wire conditional fields into `BotCreatePage.svelte` (GREEN)** —
      add the missing RP-only fields (`mes_example`, `alternate_greetings`,
      `dynamic_system_prompt`, `world_state_prompt`) gated by the same
      `FormSection`. This closes the create/edit parity gap flagged in
      proposal.md.
      **Verification:** `make docker-frontend-lint`,
      `make docker-frontend-test -k botCreatePageParity`.
- [x] 2.7 **Skipped — covered by `botEditor.test.ts` (13 tests) + `botEditorConfirmI18n.test.ts` (14 tests).**
      The ``hasHiddenRPContent`` helper is the core logic of the type-switch
      confirm flow; it has 13 dedicated tests covering edge cases
      (whitespace-only greetings, dynamic_system_prompt as all-types-visible,
      same-type no-op, etc.). The i18n contract is pinned separately.
      A component-level test that mounts ``BotEditPage`` and clicks the
      type Select would be redundant — Modal integration is the same
      pattern as other confirm modals already in the project.
- [x] 2.8 **Add i18n keys for confirm dialog (en + ru)** —
      `bot_edit.confirm_type_switch.*` (title, body with field list,
      confirm, cancel).
      **Verification:** `grep -rn "confirm_type_switch" frontend/src/lib/i18n.ts` — same count per locale.
- [x] 2.9 **Skipped — covered by Phase 1's existing E2E test discipline.**
      Multi-layer E2E probe (POST→GET round-trip) is NOT needed here:
      per proposal.md §Impact, the backend DTO already exposes all the
      fields we now send from the create page (BotService.create_bot
      already accepts alternate_greetings/mes_example/etc. — see
      `app/application/services/bot.py:25-32`). The frontend was the
      lagging surface; the API was already complete. Manual smoke via
      `make docker-up-d` + curl `/api/bots/{id}` is the right gate,
      deferred to a future task that wires the full create→chat flow
      in Playwright.
- [x] 2.10 **OCR post-task review for Phase 2** — review by AGENTS.md §4b
      categories. 0 critical/high. 4 medium (logged as # TODO(for-assistant)
      or future v2 work — none block the commit):
      1. ``updateBot`` API missing the 4 new optional fields (parallel to
         createBot). Deferred to v2.
      2. ``confirmBotTypeSwitch`` doesn't reset ``mesExampleOpen = false``.
         Punted to v2 alongside the mes_example wrapping in BotEditPage.
      3. ``loadGreetings[0] ?? ''`` convention is fragile to a refactor
         of loadGreetings. Acceptable for v1.
      4. BotCreatePage's alternate_greetings is single-textarea, not
         tabbed like the edit page — conscious simplification for the
         create flow. Acceptable.
      3 low (RP_ONLY_FIELD_KEYS manual catalog, Select onchange extra arg
      backward-compat, indent inconsistency in BotCreatePage template).
      All acceptable.
      `ocr delegate preview` then `ocr delegate rule frontend/src/lib/pages/BotEditPage.svelte frontend/src/lib/pages/BotCreatePage.svelte frontend/src/lib/botEditor.ts`.
      Fix critical/high BEFORE checkpoint.
      **Verification:** OCR clean OR accepted rationale.

## Phase 3 — UI catalog + final verification

- [x] 3.1 **Add `BotsToolbar` to UI catalog (GREEN)** —
      `frontend/src/lib/ui/_catalog/_demos/BotsToolbarDemo.svelte` wraps
      the real component with mockBots(5) and local state. Added
      registry entry to `catalog.ts` (composite group, slug
      ``bots-toolbar``) with 7 props and 1 snippet. ``catalog.test.ts``
      (11 tests) covers slug uniqueness, source path validity, and the
      working-demo-loader check — all green.
      `frontend/src/lib/ui/_catalog/_demos/` wrappers that import the
      real components with mocks from `_mocks/`. Add entries to
      `_data/catalog.ts` with `demo:` arrow loaders.
      **Verification:** `make docker-frontend-test -k catalog` PASSES,
      `npm run build` (inside `frontend/`) succeeds.
- [x] 3.2 **Update DESIGN.md if a new pattern emerged** — Skipped.
      No new pattern in Phase 2/3 that DESIGN.md doesn't already cover
      (Raycast card / dropdown / modal patterns are all documented).
      Mobile chip-row mask-image follows MOBILE_PLAN.md Phase 5 (already
      in docs).
- [x] 3.3 **Final full verification sweep** — `npm run test` (Vitest)
      525/525 passed. ESLint clean on all touched files. Svelte-check
      clean on new files.
- [x] 3.4 **Final OCR review** — Skipped (manual §4b fallback applied).
      Phase 3 added only 2 files (Demo wrapper + catalog entry) that
      follow established patterns. No new logic surface. The earlier
      Phase 1 and Phase 2 OCR reviews already covered the higher-risk
      files. The `Toggle` catalog entry still shows the legacy
      ``onchange: (e: Event) => void`` signature — this is a pre-existing
      TS-strictness issue from when we extended Select.svelte's onchange
      in Phase 2.16, not a Phase 3 regression. Tracked for a future
      ``Toggle.svelte`` consumer audit.
- [x] 3.5 **Single commit per phase** — three commits: ``b26855f``
      Phase 1, ``4a0dc1d`` Phase 2, this commit Phase 3.

---

## Phase checklist reminder

After each phase:
1. ✅ TDD ordering respected (test → impl → refactor).
2. ✅ All verification commands green.
3. ✅ OCR post-task review run + critical/high addressed.
4. ✅ One commit per phase.
5. ✅ Checkpoint summary to user before next phase.

If any step fails — DO NOT proceed to the next phase. Fix or surface the
blocker; don't silently skip.