<script lang="ts">
  import { t } from './i18n';
  import { Modal } from './ui';

  let {
    lang = 'en',
    oncancel,
    onconfirm,
    show = false,
  }: {
    lang?: string;
    oncancel?: () => void;
    onconfirm?: () => void;
    show?: boolean;
  } = $props();
</script>

<Modal bind:open={show} title={t('delete_confirm.title', lang)} size="sm" onclose={oncancel}>
  {#snippet footer()}
    <div class="flex gap-3">
      <button class="ray-btn" onclick={oncancel}>{t('delete_confirm.cancel', lang)}</button>
      <button class="ray-btn danger" onclick={onconfirm}>{t('delete_confirm.delete', lang)}</button>
    </div>
  {/snippet}
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center shrink-0">
      <span class="w-5 h-5 text-red-400">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><path
            d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
          /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg
        >
      </span>
    </div>
    <p class="text-sm text-base-content/70">{t('delete_confirm.msg', lang)}</p>
  </div>
</Modal>
