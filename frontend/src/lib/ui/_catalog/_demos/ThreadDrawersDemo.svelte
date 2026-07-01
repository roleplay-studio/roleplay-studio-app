<!-- ThreadDrawersDemo.svelte — right-aside thread list with context menu (rename/delete) + delete confirm -->
<script lang="ts">
  import ThreadDrawer from '../../../ThreadDrawer.svelte';
  import { logOnly } from '../_mocks/callbacks';
  import { mockChatThreads } from '../_mocks/threadFixtures';

  const threads = mockChatThreads(3);
  const onclose = logOnly('drawer-close');
  const onnew = logOnly('new-thread');
  const onselect = logOnly<(id: number) => void>('select-thread');
  const onrename = logOnly<(id: number, name: string) => void>('rename-thread');
  const ondelete = logOnly<(id: number) => void>('delete-thread');

  // ThreadDrawer uses api.renameThread / api.deleteThread directly.
  // For the catalog demo we monkey-patch window.fetch so the in-component
  // calls return a fake 200 OK without touching the real backend.
  const realFetch = window.fetch;
  // Type-cast RequestInfo/RequestInit to silence ESLint no-undef
  // for these DOM lib types.
  window.fetch = ((url: string | URL, init?: any) => {
    const u = typeof url === 'string' ? url : url.toString();
    if (u.includes('/api/threads/') && (init?.method === 'PATCH' || init?.method === 'DELETE')) {
      return Promise.resolve(new Response('{"ok":true}', { status: 200 }));
    }
    return realFetch(url, init);
  }) as typeof window.fetch;
</script>

<svelte:window
  on:beforeunload={() => {
    // restore real fetch when leaving the page
    window.fetch = realFetch;
  }}
/>

<div class="tdd-frame">
  <ThreadDrawer
    {threads}
    selectedThreadId={threads[0]?.id ?? null}
    {onclose}
    {onnew}
    {onselect}
    {onrename}
    {ondelete}
    lang="en"
  />
</div>

<style>
  .tdd-frame {
    /* Match the real-app viewport so the fixed aside is visible */
    height: 480px;
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    overflow: hidden;
    position: relative;
    background: var(--ray-bg-card, #ffffff);
  }
</style>
