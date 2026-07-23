<!--
  SkillPicker — multi-select chips for attaching skills to a bot.
  Phase 6 of skills-implementation plan.

  Domain-aware composite (knows about SkillDTO/BotSkillDTO), lives in
  src/lib/ not src/lib/ui/. Pattern parity with CategoryPicker but
  with ID-based selection (skill names are unique but ID is the
  stable wire identifier).

  States:
  - Available skills (all from api.listSkills) shown as unselected pills.
  - Attached skills (selected) shown with selected styling.
  - ``maxReached`` (settings.skills_max_per_bot) disables new adds.

  Pure presentation — save semantics live in the parent
  (BotEditPage), which collects the final ID list and POSTs it
  via api.updateBotSkills. We expose the chip state via
  onchange(attachedIds) for the parent to wire to its save flow.
-->
<script lang="ts">
  import type { SkillDTO } from './api';

  let {
    allSkills = [],
    attachedIds = [],
    maxReached = false,
    onchange,
  }: {
    allSkills?: SkillDTO[];
    attachedIds?: number[];
    maxReached?: boolean;
    onchange?: (ids: number[]) => void;
  } = $props();

  function toggle(id: number) {
    if (attachedIds.includes(id)) {
      onchange?.(attachedIds.filter((x) => x !== id));
      return;
    }
    if (maxReached) return; // silently ignore — parent should show a hint
    onchange?.([...attachedIds, id]);
  }
</script>

<div class="sp-field" data-testid="skill-picker" aria-labelledby="skill-picker-label">
  <div class="sp-label-row">
    <label class="sp-label" id="skill-picker-label">Skills</label>
    {#if maxReached}
      <span class="sp-hint">Max reached — remove one before adding another.</span>
    {/if}
  </div>
  {#if allSkills.length === 0}
    <div class="sp-empty">
      No skills yet. Use the Library page to create one.
    </div>
  {:else}
    <div class="sp-grid">
      {#each allSkills as skill (skill.id)}
        {@const isAttached = attachedIds.includes(skill.id)}
        <button
          class="sp-pill"
          class:selected={isAttached}
          disabled={!isAttached && maxReached}
          onclick={() => toggle(skill.id)}
          title={skill.description || skill.name}
          type="button"
        >
          <span class="sp-pill-name">{skill.name}</span>
          {#if skill.tags.length > 0}
            <span class="sp-pill-tags">{skill.tags.join(' · ')}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .sp-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .sp-label-row {
    display: flex;
    align-items: baseline;
    gap: 12px;
  }
  .sp-label {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ray-text);
  }
  .sp-hint {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    color: var(--ray-text-secondary);
  }
  .sp-empty {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    color: var(--ray-text-secondary);
    padding: 12px 14px;
    background: var(--ray-surface);
    border: 1px dashed var(--ray-border);
    border-radius: 8px;
  }
  .sp-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .sp-pill {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--ray-surface);
    border: 1px solid var(--ray-border);
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 12px;
    cursor: pointer;
    transition:
      background 0.15s,
      border-color 0.15s,
      opacity 0.15s;
  }
  .sp-pill:hover:not(:disabled) {
    background: var(--ray-surface-hover);
    border-color: var(--ray-border-strong);
  }
  .sp-pill:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .sp-pill.selected {
    background: var(--ray-accent-soft);
    border-color: var(--ray-accent);
    color: var(--ray-accent);
  }
  .sp-pill-name {
    font-weight: 500;
  }
  .sp-pill-tags {
    font-size: 10px;
    color: var(--ray-text-secondary);
    letter-spacing: 0.02em;
  }
</style>