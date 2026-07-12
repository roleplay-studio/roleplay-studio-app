<!-- LLMDebugModalsDemo.svelte — debug payload modal with model info + usage + messages JSON -->
<script lang="ts">
  import type { LLMDebugInfo, LLMUsage } from '../../../api';

  import LLMDebugModal from '../../../LLMDebugModal.svelte';
  import Button from '../../../ui/Button.svelte';
  import { logOnly } from '../_mocks/callbacks';

  let open = $state(false);
  const onclose = logOnly('close');

  const usage: LLMUsage = {
    completion_tokens: 487,
    prompt_tokens: 1208,
    total_tokens: 1695,
  };
  const debug: LLMDebugInfo = {
    max_tokens: 1024,
    messages: [
      { content: 'You are a helpful assistant.', role: 'system' },
      { content: 'Explain quantum tunneling in two sentences.', role: 'user' },
      {
        content: 'Quantum tunneling is a phenomenon where a particle passes through a...',
        role: 'assistant',
      },
    ],
    model: 'gpt-4o-mini',
    temperature: 0.7,
  };
</script>

<div class="llmd-stack">
  <Button variant="primary" onclick={() => (open = true)}>Show LLM debug</Button>
  <p class="llmd-hint">
    Modal with model line (gpt-4o-mini · temp=0.7 · max_tokens=1024), usage pills (prompt 1.2k /
    completion 487 / total 1.7k), and a syntax-highlighted JSON of the messages sent to the model.
    Esc or backdrop to close.
  </p>
</div>

{#if open}
  <LLMDebugModal {debug} {usage} state={null} {onclose} />
{/if}

<style>
  .llmd-stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .llmd-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
