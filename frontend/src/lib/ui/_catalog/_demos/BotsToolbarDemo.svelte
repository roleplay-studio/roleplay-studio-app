<!--
  BotsToolbarDemo — showcase for the BotsToolbar composite component
  (introduced by ``improve-bot-editor``). Feeds it a tiny in-memory
  bot list and exposes the controlled-component callbacks to the
  catalog's props panel via local \$state.

  We don't drive sort/filter/search through real network calls — the
  toolbar is a controlled component whose behaviour is fully owned by
  its parent, and that contract is what the catalog documents.
  Visual realism is enough: the toolbar renders, the chips toggle,
  the search input accepts text, and the user sees the result count
  beneath the search box.
-->

<script lang="ts">
  import type { BotType } from '../../../api';

  import { applyBotsFilters, type BotSortDir, type BotSortKey } from '../../../botsBrowse';
  import BotsToolbar from '../../../BotsToolbar.svelte';
  import { mockBots } from '../_mocks/botFixtures';

  // Controlled state for the demo — mirrors BotsPage.svelte's pattern.
  let sortKey: BotSortKey = $state('id');
  let sortDir: BotSortDir = $state('desc');
  let activeTypes: BotType[] = $state([]);
  let query: string = $state('');

  const bots = mockBots(5);
  const visibleBots = $derived(
    applyBotsFilters(bots, { query, sortDir, sortKey, types: activeTypes }),
  );
</script>

<div class="bots-toolbar-demo flex flex-col gap-3">
  <BotsToolbar
    activeTypes={activeTypes}
    onqueryChange={(q) => (query = q)}
    onsortChange={(k, d) => {
      sortKey = k;
      sortDir = d;
    }}
    ontypesChange={(t) => (activeTypes = t)}
    {query}
    {sortDir}
    {sortKey}
  />
  <p class="text-xs text-rp-text-secondary">
    Demo only — sort/filter/search are local state, no API calls. Showing
    {visibleBots.length} of {bots.length} mock bots.
  </p>
</div>
