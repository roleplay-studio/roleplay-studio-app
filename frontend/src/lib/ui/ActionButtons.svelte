<script lang="ts">
  const {
    actions = [] as string[],
    onaction,
  }: {
    actions?: string[];
    onaction?: (text: string) => void;
  } = $props();
</script>

{#if actions.length > 0}
  <div class="flex flex-wrap gap-1.5 mt-2.5">
    {#each actions as action (action)}
      <button
        class="w-full font-['Maple_Mono',system-ui,sans-serif] text-xs font-medium py-1.5 px-3.5 rounded-lg border
        border-violet-500/20 bg-violet-500/[0.06] text-violet-500 cursor-pointer transition-all
        duration-[120ms] ease-in-out whitespace-nowrap hover:bg-violet-500/[0.15] hover:border-violet-500/40
        hover:text-violet-600 hover:dark:text-violet-400 active:scale-[0.97]"
        onclick={() => onaction?.(action)}
      >
        {action}
      </button>
    {/each}
  </div>
{/if}

<style>
</style>
