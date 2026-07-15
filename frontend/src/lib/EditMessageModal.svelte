<script lang="ts">
  import { t } from './i18n';
  import { Input, Modal, Tabs } from './ui';

  // ``messageState`` (not ``state``) — ``state`` is a reserved
  // identifier in Svelte 5 for stores (``$state(...)``), and
  // shadowing it on a destructured $props() confuses the template
  // parser into treating the string prop as a store subscription.
  //
  // When ``messageState`` is ``null`` the modal renders a single
  // "message" tab — the message has no world-state snapshot to
  // edit (either a user turn, or an assistant turn whose state
  // update task hasn't run yet). When it carries a value, both
  // tabs are shown and the user can flip between them while
  // editing. The Save button always ships both fields so a user
  // who only touched content on the message tab still gets
  // branching fidelity on state.
  let {
    content = '',
    lang = 'en',
    messageState = null,
    onclose,
    onsave,
    show = false,
  }: {
    content?: string;
    lang?: string;
    messageState?: null | string;
    onclose?: () => void;
    onsave?: (text: string, state: null | string) => void;
    show?: boolean;
  } = $props();

  // Track the previous ``show`` value so the $effect below only
  // resets the local mirrors on the false→true transition. Capturing
  // the initial value of ``content`` inside $state() directly would
  // trip Svelte 5's "reference only the initial value" warning
  // (and would be subtly wrong if the parent ever changes the prop
  // while the modal stays open).
  let prevShow = $state(false);

  let editText = $state('');
  // Local mirror of the world-state snapshot so the user can edit
  // it without round-tripping through the parent on every keystroke.
  let editState = $state('');

  $effect(() => {
    // Reset the local mirrors whenever the modal transitions from
    // closed → open (i.e. user just opened the editor). Without
    // this guard a parent that re-uses the modal for multiple
    // messages would show the previous one's content.
    if (show && !prevShow) {
      editText = content;
      editState = messageState ?? '';
    }
    prevShow = show;
  });

  // Which top-level tab is active. Always reset to ``message`` when
  // the modal opens so the user lands on the most-touched field.
  // ``state`` tab is hidden entirely when ``messageState`` is null
  // — see the tabs[] computed below.
  let activeTab: 'message' | 'state' = $state('message');
  $effect(() => {
    if (show && !prevShow) {
      activeTab = 'message';
    }
  });

  // The two-tab segmented control is only mounted when there's a
  // state column to edit — a user-message editor shows just one
  // textarea, no clutter.
  let tabs = $derived(
    messageState === null
      ? [{ id: 'message' as const, label: t('edit_message.tab_message', lang) }]
      : [
          { id: 'message' as const, label: t('edit_message.tab_message', lang) },
          { id: 'state' as const, label: t('edit_message.tab_state', lang) },
        ],
  );
</script>

<Modal open={show} title={t('edit_message.title', lang)} size="lg" {onclose}>
  {#snippet footer()}
    <div class="flex gap-3">
      <button class="ray-btn" onclick={onclose}>{t('edit_message.cancel', lang)}</button>
      <button
        class="ray-btn primary"
        disabled={!editText.trim()}
        onclick={() => onsave?.(editText, messageState === null ? null : editState)}
        >{t('edit_message.save', lang)}</button
      >
    </div>
  {/snippet}
  <Tabs {activeTab} onchange={(id) => (activeTab = id as 'message' | 'state')} {tabs} />
  <div class="mt-4">
    {#if activeTab === 'message'}
      <Input
        textarea
        bind:value={editText}
        rows={10}
        placeholder={t('edit_message.placeholder', lang)}
        class="font-mono w-full"
      />
    {:else}
      <Input
        textarea
        bind:value={editState}
        rows={6}
        placeholder={t('edit_message.state_placeholder', lang)}
        class="font-mono w-full"
      />
      <p class="text-xs text-neko-300/60 mt-2">
        {t('edit_message.state_hint', lang)}
      </p>
    {/if}
  </div>
</Modal>
