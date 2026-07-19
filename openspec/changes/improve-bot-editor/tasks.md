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

- [ ] 2.1 **Add Vitest for `hasHiddenRPContent` helper (RED)** —
      `frontend/src/lib/__tests__/botEditorConditionalFields.test.ts`.
      Cases: empty form → false; non-empty `first_message` → true;
      non-empty `alternate_greetings[]` → true; non-empty `mes_example` →
      true; non-empty `world_state_prompt` → true; type === `rp` →
      always false (no hidden fields).
      **Verification:** `make docker-frontend-test -k hasHiddenRPContent` — must FAIL.
- [ ] 2.2 **Implement `hasHiddenRPContent` helper (GREEN)** —
      `frontend/src/lib/botEditor.ts`. Pure function over a typed form
      state object. No Svelte dependency so it's unit-testable in plain
      Vitest.
      **Verification:** `make docker-frontend-test -k hasHiddenRPContent` — must PASS.
- [ ] 2.3 **Add Vitest for `FormSection` snippet wrapper (RED)** — render
      snippet conditionally; assert children render when condition is
      true, nothing when false; assert `{#snippet}` usage is correct.
      **Verification:** `make docker-frontend-test -k FormSection` — must FAIL.
- [ ] 2.4 **Implement `FormSection` snippet wrapper (GREEN)** — tiny
      Svelte 5 component that takes a `condition: boolean` and
      `{@render children?.()}`. No new atomic primitive — lives next to
      `BotEditPage.svelte` as a local helper if reused only here.
      **Verification:** `make docker-frontend-test -k FormSection` — must PASS.
- [ ] 2.5 **Wire conditional fields into `BotEditPage.svelte` (GREEN)** —
      wrap `alternate_greetings`, `mes_example`, `world_state_prompt`,
      `scenario`, `first_message` in `FormSection` keyed on
      `formBotType === 'rp'`. On type change, call `hasHiddenRPContent`
      and open `<Modal>` confirm dialog from D3 of design.md.
      **Verification:** `make docker-frontend-lint`,
      `make docker-frontend-test -k botEditorConditionalFields`.
- [ ] 2.6 **Wire conditional fields into `BotCreatePage.svelte` (GREEN)** —
      add the missing RP-only fields (`mes_example`, `alternate_greetings`,
      `dynamic_system_prompt`, `world_state_prompt`) gated by the same
      `FormSection`. This closes the create/edit parity gap flagged in
      proposal.md.
      **Verification:** `make docker-frontend-lint`,
      `make docker-frontend-test -k botCreatePageParity`.
- [ ] 2.7 **Add Vitest for the type-switch confirm flow (RED→GREEN)** —
      simulate user changing `bot_type` from `rp` to `assistant` with
      non-empty `first_message`. Assert confirm dialog appears, cancel
      restores old type, confirm discards content and hides fields.
      **Verification:** `make docker-frontend-test -k typeSwitchConfirm` PASSES.
- [ ] 2.8 **Add i18n keys for confirm dialog (en + ru)** —
      `bot_edit.confirm_type_switch.*` (title, body with field list,
      confirm, cancel).
      **Verification:** `grep -rn "confirm_type_switch" frontend/src/lib/i18n.ts` — same count per locale.
- [ ] 2.9 **Manual smoke against backend round-trip** — start
      `make docker-up-d`, switch bot type via UI, save, reload
      `GET /api/bots/{id}`, assert round-tripped fields match form state
      for the chosen type. This catches the silent-DB-drop class of bug
      flagged in AGENTS.md §2 (no Python unit test can catch UI
      round-trip; we need a live check).
      **Verification:** `make docker-shell-backend` + `curl` returns expected fields.
- [ ] 2.10 **OCR post-task review for Phase 2** —
      `ocr delegate preview` then `ocr delegate rule frontend/src/lib/pages/BotEditPage.svelte frontend/src/lib/pages/BotCreatePage.svelte frontend/src/lib/botEditor.ts`.
      Fix critical/high BEFORE checkpoint.
      **Verification:** OCR clean OR accepted rationale.

## Phase 3 — UI catalog + final verification

- [ ] 3.1 **Add `BotsToolbar` and `FormSection` to UI catalog (GREEN)** —
      `frontend/src/lib/ui/_catalog/_demos/` wrappers that import the
      real components with mocks from `_mocks/`. Add entries to
      `_data/catalog.ts` with `demo:` arrow loaders.
      **Verification:** `make docker-frontend-test -k catalog` PASSES,
      `npm run build` (inside `frontend/`) succeeds.
- [ ] 3.2 **Update DESIGN.md if a new pattern emerged** — only if
      something the change introduced is reusable beyond this PR
      (for example a new chip-padding convention). Skip silently if no
      new pattern.
      **Verification:** `git diff --stat docs/DESIGN.md` — only if non-zero.
- [ ] 3.3 **Final full verification sweep** —
      `make docker-frontend-lint` && `make docker-frontend-test` &&
      `make docker-ruff` && `make docker-test`. All green. The
      `make docker-test` (Python) is smoke only — no backend changed,
      but it confirms we didn't break the existing baseline.
      **Verification:** all four commands exit 0.
- [ ] 3.4 **Final OCR review** — `ocr delegate preview` against the
      full set of touched files; fix any critical/high surfaced by
      `ocr delegate rule`. This is the last gate before checkpoint.
      **Verification:** OCR clean OR accepted rationale.
- [ ] 3.5 **Single commit per phase** — three commits:
      `feat(bots): add library sort/filter/search` (Phase 1),
      `feat(editor): type-aware bot form fields` (Phase 2),
      `chore(catalog): add new components to UI catalog` (Phase 3). No
      drive-by commits, no unrelated reformat.
      **Verification:** `git log --oneline -3` matches the three lines above.

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