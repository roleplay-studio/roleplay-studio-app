<!-- MessageBubblesDemo.svelte — user / assistant / streaming / with-actions / with-reasoning -->
<script lang="ts">
  import MessageBubble from '../../../MessageBubble.svelte';
  import { logOnly } from '../_mocks/callbacks';
  import { mockMessages } from '../_mocks/messageFixtures';

  const base = mockMessages(5);
  const onaction = logOnly<(t: string) => void>('action');
  const onedit = logOnly('edit');
  const ondelete = logOnly('delete');
  const onretry = logOnly('retry');
  const onregenerate = logOnly('regenerate');
  const onopendebug = logOnly('open-debug');
  const onswitchversion = logOnly<(id: number) => void>('switch-version');

  // Build variants: assistant plain, user plain, assistant streaming,
  // user with retry, assistant with versions + debug
  const assistantMsg = { ...base[0], role: 'assistant' as const };
  const userMsg = { ...base[1], role: 'user' as const };
  const streamingMsg = {
    ...base[2],
    content: '',
    role: 'assistant' as const,
  };
  const userWithRetry = { ...base[3], content: 'Failed upload.', role: 'user' as const };
  const withVersions = {
    ...base[4],
    is_active: true,
    role: 'assistant' as const,
  };
  const versions = [
    { ...base[4], id: 1, is_active: false },
    { ...base[4], id: 2, is_active: true },
    { ...base[4], id: 3, is_active: false },
  ];
</script>

<div class="mbd-stack">
  <div class="mbd-row">
    <span class="mbd-label">Assistant (plain)</span>
    <div class="mbd-frame">
      <MessageBubble botName="Aria" {onaction} {onedit} {ondelete} msg={assistantMsg} lang="en" />
    </div>
  </div>
  <div class="mbd-row">
    <span class="mbd-label">User</span>
    <div class="mbd-frame">
      <MessageBubble personaName="You" {onedit} {ondelete} msg={userMsg} lang="en" />
    </div>
  </div>
  <div class="mbd-row">
    <span class="mbd-label">Assistant streaming (empty content, isLast)</span>
    <div class="mbd-frame">
      <MessageBubble botName="Aria" msg={streamingMsg} streaming isLast lang="en" />
    </div>
  </div>
  <div class="mbd-row">
    <span class="mbd-label">User with retry (failed upload)</span>
    <div class="mbd-frame">
      <MessageBubble
        personaName="You"
        msg={userWithRetry}
        showRetry
        {onretry}
        {onedit}
        {ondelete}
        lang="en"
      />
    </div>
  </div>
  <div class="mbd-row">
    <span class="mbd-label">Assistant with versions + debug</span>
    <div class="mbd-frame">
      <MessageBubble
        botName="Aria"
        msg={withVersions}
        {versions}
        isLast
        {onregenerate}
        {onopendebug}
        {onswitchversion}
        {onedit}
        {ondelete}
        lang="en"
      />
    </div>
  </div>
</div>

<style>
  .mbd-stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .mbd-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .mbd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .mbd-frame {
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    padding: 12px 14px;
    background: var(--ray-bg-card, #ffffff);
  }
</style>
