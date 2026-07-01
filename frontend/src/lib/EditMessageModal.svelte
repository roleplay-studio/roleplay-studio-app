<script lang="ts">
  import { t } from './i18n';
  import { Input, Modal } from './ui';

  let {
    content = '',
    lang = 'en',
    onclose,
    onsave,
    show = false,
  }: {
    content?: string;
    lang?: string;
    onclose?: () => void;
    onsave?: (text: string) => void;
    show?: boolean;
  } = $props();

  let editText = $state(content);

  $effect(() => {
    if (show) editText = content;
  });
</script>

<Modal open={show} title={t('edit_message.title', lang)} size="lg" {onclose}>
  {#snippet footer()}
    <div class="flex gap-3">
      <button class="ray-btn" onclick={onclose}>{t('edit_message.cancel', lang)}</button>
      <button class="ray-btn primary" disabled={!editText.trim()} onclick={() => onsave?.(editText)}
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
</Modal>
