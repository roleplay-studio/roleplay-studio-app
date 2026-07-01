<!-- MessageContextMenusDemo.svelte — right-click context menu (copy / edit) at fixed position -->
<script lang="ts">
  import MessageContextMenu from '../../../MessageContextMenu.svelte';
  import { logOnly } from '../_mocks/callbacks';
  import { mockMessages } from '../_mocks/messageFixtures';

  const msgs = mockMessages(1);
  const msg = msgs[0];

  let pos = $state<null | { x: number; y: number }>(null);
  const onclose = logOnly('ctx-close');
  const onedit = logOnly<(m: typeof msg) => void>('ctx-edit');

  function showMenu(e: MouseEvent) {
    e.preventDefault();
    pos = { x: e.clientX, y: e.clientY };
  }
</script>

<div class="mcmd-stack">
  <div class="mcmd-target" oncontextmenu={showMenu} role="button" tabindex="0">
    <p>Right-click anywhere in this box to open the context menu</p>
    <p class="mcmd-hint">The menu auto-closes on Esc / outside click / scroll.</p>
  </div>
  <p class="mcmd-msg-preview">Message: "{msg.content.slice(0, 60)}..."</p>
</div>

<MessageContextMenu {msg} position={pos} {onclose} {onedit} />

<style>
  .mcmd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .mcmd-target {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 140px;
    border: 2px dashed var(--ray-border-subtle, rgba(255, 255, 255, 0.08));
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    cursor: context-menu;
    user-select: none;
  }
  .mcmd-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 4px 0 0;
  }
  .mcmd-msg-preview {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
