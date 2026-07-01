<!-- ChatHeadersDemo.svelte — chat header with bot info + action menu (new thread, summarize, export, edit, delete) -->
<script lang="ts">
  import ChatHeader from '../../../ChatHeader.svelte';
  import { logOnly } from '../_mocks/callbacks';

  const onbotClick = logOnly('bot-click');
  const ontoggleThreads = logOnly('toggle-threads');
  const onnewthread = logOnly('new-thread');
  const oncompress = logOnly('compress');
  const onexport = logOnly('export');
  const oneditbot = logOnly('edit-bot');
  const ondeleteThread = logOnly('delete-thread');
</script>

<div class="chd-stack">
  <span class="chd-label">With summary active</span>
  <ChatHeader
    botName="Aria the Wanderer"
    botAvatarPath={null}
    messageCount={42}
    totalTokens={8200}
    hasSummary
    lang="en"
    {onbotClick}
    {ontoggleThreads}
    {onnewthread}
    {oncompress}
    {onexport}
    {oneditbot}
    {ondeleteThread}
  />
  <span class="chd-label">No summary yet</span>
  <ChatHeader
    botName="Code Helper"
    botAvatarPath={null}
    messageCount={7}
    totalTokens={350}
    lang="en"
    {onbotClick}
    {ontoggleThreads}
  />
</div>

<style>
  .chd-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .chd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  /* Inset the header so the shadow doesn't hit our container edge */
  :global(.chd-stack > header) {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    overflow: visible;
  }
</style>
