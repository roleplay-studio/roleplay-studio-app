<!-- GlobalDropZonesDemo.svelte — visual reference + a contained "test drop" target that triggers a fake drag state -->
<script lang="ts">
  import GlobalDropZone from '../../../GlobalDropZone.svelte';

  // GlobalDropZone listens on the WINDOW for drag events. To demo it
  // without triggering a real character-card import, we provide a
  // mock for api.importBot via window.fetch interceptor — the modal
  // overlay shows the drop zone state visually, and the file-import
  // POST is intercepted to return id 999 (so the redirect to
  // /bots/999/edit is a no-op for our hash router).
  const realFetch = window.fetch;
  // The catalog mocks the underlying POST (import bot) to avoid
  // hitting the backend. Type-cast RequestInfo/RequestInit to silence
  // ESLint no-undef for these DOM lib types.
  window.fetch = ((url: string | URL, init?: any) => {
    const u = typeof url === 'string' ? url : url.toString();
    if (u.includes('/api/bots/import') && init?.method === 'POST') {
      return Promise.resolve(new Response('{"id":999}', { status: 200 }));
    }
    return realFetch(url, init);
  }) as typeof window.fetch;
</script>

<svelte:window
  on:beforeunload={() => {
    window.fetch = realFetch;
  }}
/>

<div class="gzd-stack">
  <div class="gzd-frame">
    <p class="gzd-headline">Drop a file anywhere in this area to see the overlay</p>
    <p class="gzd-hint">
      GlobalDropZone attaches drag/drop listeners to <code>window</code>, so a real file drop
      anywhere on the page would normally show the full-window overlay AND trigger
      <code>api.importBot()</code>. In this demo the POST is mocked to return id 999 (no real import
      happens).
    </p>
    <p class="gzd-hint">
      Try <strong>dragging a text file</strong> into the dashed box below to observe the overlay state
      visually:
    </p>
    <div class="gzd-target">📁 Drop a .json / .png / .webp file here</div>
  </div>
</div>

<!-- Mount the component (no visual output unless drag is active) -->
<GlobalDropZone />

<style>
  .gzd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .gzd-frame {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 16px;
    border: 1px solid var(--ray-border-subtle, rgba(255, 255, 255, 0.04));
    border-radius: 10px;
    background: var(--ray-bg-card, #ffffff);
  }
  .gzd-headline {
    font-family: 'Maple Mono', monospace;
    font-size: 13px;
    color: var(--ray-text);
    margin: 0;
  }
  .gzd-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
    line-height: 1.5;
  }
  .gzd-target {
    margin-top: 8px;
    padding: 32px;
    text-align: center;
    border: 2px dashed var(--ray-border-subtle, rgba(0, 0, 0, 0.12));
    border-radius: 10px;
    font-family: 'Maple Mono', monospace;
    font-size: 12px;
    color: var(--ray-text-secondary);
    background: var(--ray-bg-subtle, rgba(0, 0, 0, 0.02));
  }
</style>
