<!--
  SkillsLibraryPage — global library CRUD UI. Phase 7.

  Lets operators:
  - Browse / search / tag-filter the GlobalSkill catalog
  - Create a new skill (modal form with name / description /
    instruction / tags)
  - Edit an existing skill (re-open the modal form)
  - Delete a skill (with 409 attached_to confirmation modal)

  Search: case-insensitive substring match against name +
  description. Same semantics as the backend's list_all(q=...)
  so the front-end never has to round-trip for fuzzy matching.
  We deliberately don't use fuse.js because the catalog is small
  (hand-curated, ~10-50 records); a fuzzy index would be premature
  optimisation.

  Tag filter: a row of chip toggles. Multiple-select OR
  semantics ("show skills matching ANY of the selected tags").

  Save / delete semantics:
  - createSkill returns id; we then refetch.
  - updateSkill uses partial fields (only supplied ones are
    touched server-side; SkillService.update_skill supports
    field-by-field).
  - deleteSkill throws ApiError(409) with attached_to when the
    skill is still in use; we render a confirmation modal.

  Layout: a top-bar with search + filter chips, then a card
  grid. Each card exposes Edit / Delete buttons. Card preview
  shows description + tags + a truncated instruction.
-->
<script lang="ts">
  import { onMount } from 'svelte';

  import { api, ApiError, type SkillDTO } from '../api';
  import { Button, Card, Input, Modal, Textarea } from '../ui';
  import { filterSkills } from '../utils/filterSkills';

  // ── State ──────────────────────────────────────────────────────────
  let allSkills: SkillDTO[] = $state([]);
  let loading = $state(true);
  let errorMsg: null | string = $state(null);

  let searchQuery = $state('');
  let selectedTags: string[] = $state([]);

  // Modal form state — open=true when form is visible.
  let formOpen = $state(false);
  let formMode: 'create' | 'edit' = $state('create');
  let editingId: null | number = $state(null);
  let formName = $state('');
  let formDescription = $state('');
  let formInstruction = $state('');
  let formTagsCsv = $state('');
  let saving = $state(false);
  let formError: null | string = $state(null);

  // Delete-confirmation state.
  let conflictAttachedTo: null | number[] = $state(null);

  // ── Derived ────────────────────────────────────────────────────────
  /** All tags from the library, lowercased + deduped + sorted for
   *  stable chip rendering. */
  const allTags: string[] = $derived(
    Array.from(
      new Set(
        allSkills
          .flatMap((s: SkillDTO) => s.tags)
          .map((t: string) => t.toLowerCase())
          .filter(Boolean)
      )
    ).sort()
  );

  const filteredSkills: SkillDTO[] = $derived.by(() =>
    filterSkills(allSkills, searchQuery, selectedTags)
  );

  // ── Helpers ───────────────────────────────────────────────────────

  function toggleTag(tag: string) {
    selectedTags = selectedTags.includes(tag)
      ? selectedTags.filter((t) => t !== tag)
      : [...selectedTags, tag];
  }

  // ── Data ops ───────────────────────────────────────────────────────
  async function refresh() {
    loading = true;
    errorMsg = null;
    try {
      allSkills = await api.listSkills();
    } catch (e: unknown) {
      errorMsg = e instanceof Error ? e.message : 'Failed to load skills';
    } finally {
      loading = false;
    }
  }

  onMount(refresh);

  function openCreate() {
    formMode = 'create';
    editingId = null;
    formName = '';
    formDescription = '';
    formInstruction = '';
    formTagsCsv = '';
    formError = null;
    formOpen = true;
  }

  function openEdit(skill: SkillDTO) {
    formMode = 'edit';
    editingId = skill.id;
    formName = skill.name;
    formDescription = skill.description;
    formInstruction = skill.instruction;
    formTagsCsv = skill.tags.join(', ');
    formError = null;
    formOpen = true;
  }

  function closeForm() {
    formOpen = false;
    editingId = null;
    formError = null;
  }

  async function saveForm() {
    if (!formName.trim() || !formInstruction.trim()) {
      formError = 'Name and instruction are required.';
      return;
    }
    saving = true;
    formError = null;
    const tags = formTagsCsv
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      if (formMode === 'create') {
        await api.createSkill({
          description: formDescription.trim(),
          instruction: formInstruction.trim(),
          name: formName.trim(),
          tags,
        });
      } else if (formMode === 'edit' && editingId !== null) {
        await api.updateSkill(editingId, {
          description: formDescription,
          instruction: formInstruction,
          name: formName,
          tags,
        });
      }
      await refresh();
      closeForm();
    } catch (e: unknown) {
      formError = e instanceof Error ? e.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  async function confirmDelete(skill: SkillDTO) {
    conflictAttachedTo = null;
    try {
      await api.deleteSkill(skill.id);
      await refresh();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409 && e.attached_to) {
        conflictAttachedTo = e.attached_to;
      } else {
        errorMsg = e instanceof Error ? e.message : 'Delete failed';
      }
    }
  }
</script>

<div class="slp-page">
  <header class="slp-header">
    <h1>Skills library</h1>
    <Button variant="primary" onclick={openCreate}>+ New skill</Button>
  </header>

  <div class="slp-toolbar">
    <div class="slp-search-row">
      <Input
        placeholder="Search by name or description…"
        bind:value={searchQuery}
      />
    </div>
    {#if allTags.length > 0}
      <div class="slp-tag-row">
        {#each allTags as tag (tag)}
          <button
            class="slp-tag-chip"
            class:selected={selectedTags.includes(tag)}
            onclick={() => toggleTag(tag)}
            type="button"
          >
            {tag}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if loading}
    <p class="slp-empty">Loading…</p>
  {:else if errorMsg}
    <p class="slp-error" role="alert">{errorMsg}</p>
  {:else if filteredSkills.length === 0}
    <p class="slp-empty">
      {#if allSkills.length === 0}
        No skills yet. Click "+ New skill" to create one.
      {:else}
        No skills match the current filters.
      {/if}
    </p>
  {:else}
    <div class="slp-grid">
      {#each filteredSkills as skill (skill.id)}
        <Card>
          <div class="slp-card">
            <header>
              <h3>{skill.name}</h3>
              {#if skill.tags.length > 0}
                <div class="slp-card-tags">
                  {#each skill.tags as tag (tag)}
                    <span class="slp-tag-mini">{tag}</span>
                  {/each}
                </div>
              {/if}
            </header>
            <p class="slp-card-desc">{skill.description || '(no description)'}</p>
            <pre class="slp-card-instruction">{skill.instruction.slice(0, 200)}{skill.instruction.length > 200 ? '…' : ''}</pre>
            <footer class="slp-card-actions">
              <Button variant="ghost" onclick={() => openEdit(skill)}>Edit</Button>
              <Button variant="error" onclick={() => confirmDelete(skill)}>Delete</Button>
            </footer>
          </div>
        </Card>
      {/each}
    </div>
  {/if}
</div>

<!-- Inline form modal -->
<Modal
  open={formOpen}
  onclose={closeForm}
  title={formMode === 'edit' ? 'Edit skill' : 'New skill'}
>
  <div class="slp-form">
    <label class="slp-form-field">
      <span>Name</span>
      <Input bind:value={formName} />
    </label>
    <label class="slp-form-field">
      <span>Description (≤300 chars)</span>
      <Textarea bind:value={formDescription} rows={2} />
    </label>
    <label class="slp-form-field">
      <span>Instruction (markdown, ≤4000 chars)</span>
      <Textarea bind:value={formInstruction} rows={8} />
    </label>
    <label class="slp-form-field">
      <span>Tags (comma-separated)</span>
      <Input bind:value={formTagsCsv} placeholder="tone, dialog" />
    </label>
    {#if formError}
      <p class="slp-form-error" role="alert">{formError}</p>
    {/if}
    <div class="slp-form-actions">
      <Button variant="ghost" onclick={closeForm}>Cancel</Button>
      <Button variant="primary" onclick={saveForm} disabled={saving}>
        {saving ? 'Saving…' : 'Save'}
      </Button>
    </div>
  </div>
</Modal>

<!-- 409 delete-conflict modal -->
<Modal
  open={conflictAttachedTo !== null}
  onclose={() => (conflictAttachedTo = null)}
  title="Cannot delete — skill is in use"
>
  <p>
    This skill is attached to {conflictAttachedTo?.length ?? 0} bot(s).
    Detach it from those bots first, then try again.
  </p>
  {#if conflictAttachedTo && conflictAttachedTo.length > 0}
    <ul class="slp-conflict-list">
      {#each conflictAttachedTo as botId (botId)}
        <li>Bot #{botId}</li>
      {/each}
    </ul>
  {/if}
  {#snippet footer()}
    <Button variant="primary" onclick={() => (conflictAttachedTo = null)}>OK</Button>
  {/snippet}
</Modal>

<style>
  .slp-page {
    padding: 20px;
    max-width: 960px;
    margin: 0 auto;
  }
  .slp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .slp-header h1 {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 22px;
    margin: 0;
  }
  .slp-toolbar {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 20px;
  }
  .slp-search-row {
    max-width: 360px;
  }
  .slp-tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .slp-tag-chip {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    padding: 4px 10px;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border);
    border-radius: 86px;
    color: var(--ray-text-secondary);
    cursor: pointer;
  }
  .slp-tag-chip.selected {
    background: var(--ray-accent-soft);
    border-color: var(--ray-accent);
    color: var(--ray-accent);
  }
  .slp-empty,
  .slp-error {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    color: var(--ray-text-secondary);
    padding: 32px;
    text-align: center;
  }
  .slp-error {
    color: hsl(0, 70%, 55%);
  }
  .slp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
  .slp-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
  }
  .slp-card header h3 {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    margin: 0;
  }
  .slp-card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }
  .slp-tag-mini {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 10px;
    padding: 2px 6px;
    background: var(--ray-surface-hover);
    color: var(--ray-text-secondary);
    border-radius: 4px;
  }
  .slp-card-desc {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text-secondary);
    margin: 0;
  }
  .slp-card-instruction {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    background: var(--ray-surface);
    border-radius: 6px;
    padding: 8px;
    margin: 0;
    color: var(--ray-text-secondary);
    white-space: pre-wrap;
    overflow: hidden;
  }
  .slp-card-actions {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
    margin-top: auto;
  }
  .slp-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .slp-form-field {
    display: flex;
    flex-direction: column;
    font-size: 12px;
    color: var(--ray-text-secondary);
    gap: 4px;
  }
  .slp-form-error {
    color: hsl(0, 70%, 55%);
    font-size: 12px;
  }
  .slp-form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .slp-conflict-list {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    list-style: none;
    padding: 8px 0;
    margin: 0;
  }
</style>