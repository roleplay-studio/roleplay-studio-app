<!-- PersonaSelectModalsDemo.svelte — persona picker (select existing or create new) for a new chat -->
<script lang="ts">
  import PersonaSelectModal from '../../../PersonaSelectModal.svelte';
  import Button from '../../../ui/Button.svelte';
  import { logOnly } from '../_mocks/callbacks';
  import { mockPersonas } from '../_mocks/personaFixtures';

  const personas = mockPersonas(3);
  let showChat = $state(false);
  let showImport = $state(false);
  const onselect = logOnly<(id: number) => void>('select-persona');
  const onclose = logOnly('close');

  // PersonaSelectModal uses api.createPersona / getPersona / createThread
  // directly. Monkey-patch fetch to no-op so the demo doesn't hit the
  // backend. After the demo, restore the real fetch.
  const realFetch = window.fetch;
  // Type-cast RequestInfo/RequestInit to silence ESLint no-undef
  // for these DOM lib types (the project has no DOM lib globals
  // registered in eslint.config.js).
  window.fetch = ((url: string | URL, init?: any) => {
    const u = typeof url === 'string' ? url : url.toString();
    if (u.includes('/api/personas') && init?.method === 'POST') {
      return Promise.resolve(new Response('{"id":999}', { status: 200 }));
    }
    if (u.includes('/api/personas/')) {
      return Promise.resolve(
        new Response('{"id":999,"name":"New","description":""}', { status: 200 }),
      );
    }
    if (u.includes('/api/bots/') && u.includes('/threads') && init?.method === 'POST') {
      return Promise.resolve(new Response('{"id":555}', { status: 200 }));
    }
    return realFetch(url, init);
  }) as typeof window.fetch;
</script>

<svelte:window
  on:beforeunload={() => {
    window.fetch = realFetch;
  }}
/>

<div class="psmd-stack">
  <div class="psmd-row">
    <span class="psmd-label">Mode: chat (start a new chat)</span>
    <Button variant="primary" onclick={() => (showChat = true)}>Pick persona &amp; chat</Button>
  </div>
  <div class="psmd-row">
    <span class="psmd-label">Mode: import</span>
    <Button variant="secondary" onclick={() => (showImport = true)}>Import with persona</Button>
  </div>
  <p class="psmd-hint">
    In create-form mode (click the dashed "+ New persona" button inside the modal), a POST to <code
      >/api/personas</code
    > is mocked to return id 999.
  </p>
</div>

<PersonaSelectModal
  show={showChat}
  botId={1}
  mode="chat"
  {personas}
  {onselect}
  onclose={() => {
    onclose();
    showChat = false;
  }}
  lang="en"
/>

<PersonaSelectModal
  show={showImport}
  botId={1}
  mode="import"
  {personas}
  {onselect}
  onclose={() => {
    onclose();
    showImport = false;
  }}
  lang="en"
/>

<style>
  .psmd-stack {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .psmd-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .psmd-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-width: 240px;
  }
  .psmd-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 0;
  }
</style>
