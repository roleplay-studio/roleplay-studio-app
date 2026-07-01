<script lang="ts">
  import { type MetadataEntry } from '../utils/parseMetadata';

  const {
    entries = [] as MetadataEntry[],
  }: {
    entries?: MetadataEntry[];
  } = $props();

  const STATS_COLORS = [
    '#8b5cf6',
    '#06b6d4',
    '#f59e0b',
    '#ef4444',
    '#10b981',
    '#f97316',
    '#3b82f8',
    '#ec4899',
  ];

  function colorForKey(key: string): string {
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
      hash = key.charCodeAt(i) + ((hash << 5) - hash);
    }
    return STATS_COLORS[Math.abs(hash) % STATS_COLORS.length];
  }

  function maxValueFor(val: number): number {
    if (val <= 0) return 100;
    if (val < 50) return 50;
    if (val <= 100) return 100;
    if (val < 500) return 500;
    if (val < 1000) return 1000;
    return val <= 10000 ? 10000 : val;
  }
</script>

{#if entries.length > 0}
  <div class="game-stats">
    <div class="gs-grid">
      {#each entries as entry (entry.key)}
        <div class="gs-item">
          <div class="gs-header">
            <span class="gs-label">{entry.displayKey}</span>
            {#if entry.isNumeric}<span class="gs-value">{entry.value}</span>{:else}{/if}
          </div>
          {#if entry.isNumeric}
            {@const color = colorForKey(entry.key)}
            {@const maxVal = maxValueFor(entry.value as number)}
            <div class="gs-bar-track">
              <div
                class="gs-bar-fill"
                style="width: {Math.min(
                  ((entry.value as number) / maxVal) * 100,
                  100,
                )}%; background: {color};"
              ></div>
            </div>
          {:else}
            {@const color = colorForKey(entry.key)}
            <div class="gs-badge" style="background: {color}22; color: {color};">{entry.value}</div>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .game-stats {
    margin-top: 8px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(139, 92, 246, 0.04);
    border: 1px solid rgba(139, 92, 246, 0.1);
    font-family: 'Maple Mono', system-ui, sans-serif;
  }
  .gs-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 14px 20px;
  }
  .gs-item {
    flex: 1 1 100px;
    min-width: 100px;
    max-width: 200px;
  }
  .gs-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 3px;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    color: var(--mb-text-secondary, #9c9c9d);
  }
  .gs-value {
    margin-left: auto;
    font-weight: 600;
    color: var(--mb-text, #f9f9f9);
    font-size: 12px;
  }
  .gs-bar-track {
    height: 4px;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.06);
    overflow: hidden;
  }
  .gs-bar-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }
  .gs-badge {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    /*white-space: nowrap;*/
    /*overflow: hidden;*/
    text-overflow: ellipsis;
    max-width: 100%;
  }
</style>
