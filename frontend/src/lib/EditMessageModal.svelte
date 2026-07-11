<script lang="ts">
  import { t } from './i18n';
  import { Input, Modal } from './ui';

  // ``messageState`` (not ``state``) — ``state`` is a reserved
  // identifier in Svelte 5 for stores (``$state(...)``), and
  // shadowing it on a destructured $props() confuses the template
  // parser into treating the string prop as a store subscription.
  let {
    content = '',
    messageState = null,
    lang = 'en',
    onclose,
    onsave,
    show = false,
  }: {
    content?: string;
    lang?: string;
    messageState?: null | string;
    onclose?: () => void;
    onsave?: (text: string, state: string | null) => void;
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
  <Input
    textarea
    bind:value={editText}
    rows={10}
    placeholder={t('edit_message.placeholder', lang)}
    class="font-mono w-full"
  />
  {#if messageState !== null}
    <div class="mt-4">
      <label class="block text-xs text-neko-300/80 mb-1 font-medium">
        {t('edit_message.state_label', lang)}
      </label>
      <Input
        textarea
        bind:value={editState}
        rows={4}
        placeholder={t('edit_message.state_placeholder', lang)}
        class="font-mono w-full"
      />
      <p class="text-xs text-neko-300/60 mt-1">
        {t('edit_message.state_hint', lang)}
      </p>
    </div>
  {/if}
</Modal>
