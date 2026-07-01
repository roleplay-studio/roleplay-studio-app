<!-- BotCardsDemo.svelte — BotCard grid with mock bots + actions + click handler -->
<script lang="ts">
  import BotCard from '../../../BotCard.svelte';
  import { mockBots } from '../_mocks/botFixtures';
  import { logOnly } from '../_mocks/callbacks';

  const bots = mockBots(3);
  const onchat = logOnly<(b: (typeof bots)[number]) => void>('chat');
  const onedit = logOnly<(b: (typeof bots)[number]) => void>('edit');
  const onexport = logOnly<(b: (typeof bots)[number], f: 'json' | 'png') => void>('export');
  const ondelete = logOnly<(b: (typeof bots)[number]) => void>('delete');
  const onclick = logOnly<(b: (typeof bots)[number]) => void>('click');
</script>

<div class="bcd-grid">
  {#each bots as bot (bot.id)}
    <BotCard {bot} showActions {onchat} {onclick} {onedit} {onexport} {ondelete} />
  {/each}
</div>

<style>
  .bcd-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
  }
</style>
