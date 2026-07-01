<!-- GameStatsDemo.svelte — GameStats grid showing numeric + string metadata entries -->
<script lang="ts">
  import type { MetadataEntry } from '../../../utils/parseMetadata';

  import GameStats from '../../GameStats.svelte';
</script>

<div class="gst-stack">
  <div class="gst-row">
    <span class="gst-label">Numeric stats (bars)</span>
    <GameStats
      entries={[
        { displayKey: 'HP', isNumeric: true, key: 'hp', value: 87 },
        { displayKey: 'MP', isNumeric: true, key: 'mp', value: 42 },
        { displayKey: 'XP', isNumeric: true, key: 'xp', value: 1340 },
        { displayKey: 'Gold', isNumeric: true, key: 'gold', value: 250 },
      ] satisfies MetadataEntry[]}
    />
  </div>
  <div class="gst-row">
    <span class="gst-label">String stats (badges)</span>
    <GameStats
      entries={[
        { displayKey: 'Class', isNumeric: false, key: 'class', value: 'Mage' },
        { displayKey: 'Race', isNumeric: false, key: 'race', value: 'Elf' },
        { displayKey: 'Guild', isNumeric: false, key: 'guild', value: 'Arcane' },
      ] satisfies MetadataEntry[]}
    />
  </div>
  <div class="gst-row">
    <span class="gst-label">Mixed</span>
    <GameStats
      entries={[
        { displayKey: 'HP', isNumeric: true, key: 'hp', value: 95 },
        { displayKey: 'MP', isNumeric: true, key: 'mp', value: 60 },
        { displayKey: 'Class', isNumeric: false, key: 'class', value: 'Warrior' },
        { displayKey: 'Level', isNumeric: true, key: 'level', value: 12 },
      ] satisfies MetadataEntry[]}
    />
  </div>
</div>

<style>
  .gst-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .gst-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .gst-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
</style>
