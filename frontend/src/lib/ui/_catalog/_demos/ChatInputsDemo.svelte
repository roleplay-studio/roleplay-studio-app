<!-- ChatInputsDemo.svelte — RP vs assistant input, with bold-action / file-upload / streaming states -->
<script lang="ts">
  import ChatInput from '../../../ChatInput.svelte';
  import { logOnly } from '../_mocks/callbacks';

  const onsend = logOnly<(text: string, fileIds: number[]) => void>('send');
  const onstop = logOnly('stop');
  let streaming = $state(true);
</script>

<div class="cid-stack">
  <div class="cid-group">
    <span class="cid-label">RP bot (bold action, no file upload)</span>
    <ChatInput botId={1} threadId={1} botType="rp" {onsend} lang="en" />
  </div>
  <div class="cid-group">
    <span class="cid-label">Assistant bot (file upload enabled)</span>
    <ChatInput botId={2} threadId={2} botType="assistant" {onsend} lang="en" />
  </div>
  <div class="cid-group">
    <span class="cid-label">Streaming (stop button instead of send)</span>
    <ChatInput botId={1} threadId={1} botType="rp" {streaming} {onstop} lang="en" />
  </div>
</div>

<style>
  .cid-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .cid-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .cid-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  :global(.cid-group .ci-wrap) {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    overflow: hidden;
  }
</style>
