<!-- BotPreviewPage.svelte — landing page for a bot before chatting.
     Shows a hero with bot avatar + categories + name, a primary
     Start Chat CTA, a hero actions popup (top-right ⋯) with
     Edit Bot + Import Chat (extensible to more actions later),
     the bot description, and a recent threads tree at the bottom
     (with fork support).

     Tailwind v4 — colors via ``bg-[var(--ray-*)]`` arbitrary
     value syntax. The two token systems (--ray-* from DESIGN.md
     and --color-surface-* from @theme) coexist by design — see
     app.css and DESIGN.md "Colors". The custom <style> block at
     the bottom owns only the pieces Tailwind can't reasonably
     express (hero overlay gradient, Raycast double-ring shadow
     on cards). -->
<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { api, API_BASE, type Bot, type Persona } from '../api';
  import { currentLang, t } from '../i18n';
  import PersonaSelectModal from '../PersonaSelectModal.svelte';
  import ThreadTree from '../ThreadTree.svelte';
  import { GeneratedAvatar, Loading } from '../ui';

  const { botId = '0' }: { botId?: string } = $props();

  let lang = $state('en');
  let bot: Bot | null = $state(null);
  let loading = $state(true);
  let showPersonaModal = $state(false);
  let recentThreads = $state<Awaited<ReturnType<typeof api.listBotThreads>>>([]);
  let unsubLang: (() => void) | undefined;

  // Import state — the popup action calls startImport() which
  // triggers the hidden <input type="file"> click; we don't have
  // a UI affordance for loading (the file picker is OS-native),
  // so importLoading is gone. Keep importError for the inline
  // banner above Start Chat and importPersonaId for the persona
  // modal flow.
  let importing = $state(false);
  let importPersonaId: null | number = $state(null);
  let fileInput: HTMLInputElement | undefined = $state();
  let importError = $state('');

  // ── Hero actions popover (Edit Bot, Import Chat, ...) ───────
  // Holds a list of secondary actions on the bot. Currently just
  // two — edit + import — but the pattern (popup-menu in hero,
  // glass overlay, click-outside to close) is the canonical place
  // for any future per-bot utility (Export, Delete, Duplicate,
  // Share, ...). Don't grow the left-column CTAs; add a row here.
  let actionsOpen = $state(false);
  let actionsRoot: HTMLDivElement | undefined = $state();
  let lastClosedAt = $state(0);

  function avatarUrl(path: null | string): null | string {
    if (!path) return null;
    return `${API_BASE}${path}`;
  }

  let personas: Persona[] = $state([]);

  onMount(async () => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    try {
      const id = parseInt(botId);
      if (id) {
        const [b, personaList, threads] = await Promise.all([
          api.getBot(id),
          api.listPersonas(),
          api.listBotThreads(id),
        ]);
        bot = b;
        personas = personaList;
        recentThreads = threads;
      }
    } catch (e) {
      console.error('Failed to load bot:', e);
    } finally {
      loading = false;
    }
  });

  onDestroy(() => {
    unsubLang?.();
  });

  // ── Actions popover controls ───────────────────────────────
  function toggleActions() {
    // Defensive: prevent the same click that closed the popup
    // from immediately reopening it (mousedown toggles actionsOpen
    // to false via the click-outside handler, then the original
    // button onclick fires and flips it back to true).
    if (actionsOpen && Date.now() - lastClosedAt < 100) return;
    actionsOpen = !actionsOpen;
  }
  function closeActions() {
    if (actionsOpen) {
      actionsOpen = false;
      lastClosedAt = Date.now();
    }
  }
  function editBotFromMenu() {
    closeActions();
    editBot();
  }
  function importChatFromMenu() {
    closeActions();
    startImport();
  }

  // Click-outside + Escape close — one shared listener handles
  // both popovers (right now only the actions menu exists, but
  // the pattern stays consistent with ChatHeader.svelte).
  $effect(() => {
    if (!actionsOpen) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (actionsRoot && !actionsRoot.contains(target)) closeActions();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeActions();
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  });

  function goBack() {
    window.location.hash = '#/';
  }

  function editBot() {
    if (!bot) return;
    window.location.hash = `/bots/${bot.id}/edit`;
  }

  function onNewThread(threadId: number) {
    showPersonaModal = false;
    window.location.hash = `/chat?bot=${bot!.id}&thread=${threadId}`;
  }

  function openThread(threadId: number) {
    window.location.hash = `/chat?bot=${bot!.id}&thread=${threadId}`;
  }

  // ── Import chat ──

  function startImport() {
    importing = true;
    importError = '';
    showPersonaModal = true;
  }

  function onImportPersonaSelected(personaId: number) {
    importPersonaId = personaId;
    showPersonaModal = false;
    setTimeout(() => fileInput?.click(), 150);
  }

  async function onFilePicked(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file || !bot) return;

    importError = '';
    try {
      const result = await api.importChat(bot.id, file, importPersonaId);
      // Redirect after brief delay
      setTimeout(() => {
        window.location.hash = `/chat?bot=${bot!.id}&thread=${result.thread_id}`;
      }, 600);
    } catch (e: unknown) {
      const err = e as { detail?: string; message?: string };
      importError = err.detail || err.message || t('bot_preview.import_failed', lang);
    } finally {
      importing = false;
      target.value = '';
    }
  }

  // Bot-type badge: small color-coded label that signals the
  // bot's mode (RP = full roleplay, Assistant = utility, Agent =
  // tool-using). Colors map to existing semantic tokens — no new
  // hues introduced.
  function botTypeVariant(type: string): { label: string; toneClass: string } {
    if (type === 'assistant') {
      return { label: 'Assistant', toneClass: 'text-[var(--ray-green)]' };
    }
    if (type === 'agent') {
      return { label: 'Agent', toneClass: 'text-[var(--ray-yellow)]' };
    }
    return { label: 'RP', toneClass: 'text-[var(--ray-blue)]' };
  }
  const typeBadge = $derived.by(() => {
    if (!bot) return { label: '', toneClass: '' };
    return botTypeVariant(bot.bot_type);
  });
</script>

<div class="bp-page min-h-screen text-rp-text">
  {#if loading}
    <div class="flex justify-center py-20">
      <Loading size="lg" />
    </div>
  {:else if !bot}
    <div class="px-4 py-20 text-center">
      <p class="mb-2 text-[16px] text-[var(--ray-text-secondary)]">
        {t('bot_preview.not_found', lang)}
      </p>
      <button
        class="cursor-pointer backdrop-blur-sm font-[Maple_Mono,system-ui,sans-serif] text-[14px] hover:opacity-80"
        onclick={goBack}
        type="button"
      >
        ← {t('bot_preview.back', lang)}
      </button>
    </div>
  {:else}
    <!-- ─── Hero ────────────────────────────────────────────── -->
    <div class="bp-hero relative h-[280px] w-full overflow-hidden">
      {#if bot.avatar_path}
        <img
          src={avatarUrl(bot.avatar_path)}
          alt={bot.name}
          class="bp-hero-img h-full w-full object-cover object-top"
        />
      {:else}
        <div class="bp-hero-placeholder flex h-full w-full items-center justify-center">
          <GeneratedAvatar name={bot.name} shape="square" block />
        </div>
      {/if}
      <div class="bp-hero-overlay pointer-events-none absolute inset-x-0 bottom-0 z-1 h-[70%]"></div>

      <!-- Hero actions (top-right, glass button + popup menu). Sits
         before the back button visually — back is on the left,
         actions are on the right; the eye reads "navigation" on
         the left and "operations on this bot" on the right. The
         popup mirrors the ChatHeader pattern: glass overlay,
         click-outside + Escape close, single shared $effect. -->
      <div
        class="absolute right-5 top-5 z-3"
        bind:this={actionsRoot}
      >
        <button
          class="bp-actions-btn flex backdrop-blur-sm h-10 w-10 cursor-pointer items-center justify-center rounded-lg border border-white/50 shadow text-rp-text transition-all duration-150 ease-out hover:border-white/50"
          class:bp-actions-btn--open={actionsOpen}
          onclick={toggleActions}
          aria-label={t('bot_preview.actions_menu', lang)}
          aria-haspopup="true"
          aria-expanded={actionsOpen}
          type="button"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
            ><circle cx="12" cy="5" r="2"></circle><circle cx="12" cy="12" r="2"></circle><circle
              cx="12"
              cy="19"
              r="2"
            ></circle></svg
          >
        </button>
        {#if actionsOpen}
          <div
            class="bp-actions-popup"
            role="menu"
            aria-label={t('bot_preview.actions_menu', lang)}
          >
            <button
              class="bp-actions-item"
              role="menuitem"
              type="button"
              onclick={editBotFromMenu}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                ><path d="M12 20h9"></path><path
                  d="M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4 12.5-12.5z"
                ></path></svg
              >
              <span>{t('bot_preview.edit_bot', lang)}</span>
            </button>
            <button
              class="bp-actions-item"
              role="menuitem"
              type="button"
              onclick={importChatFromMenu}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                ><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"></path><polyline
                  points="17 8 12 3 7 8"
                ></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg
              >
              <span>{t('bot_preview.import_chat', lang)}</span>
            </button>
          </div>
        {/if}
      </div>

      <!-- Back button (top-left, glass) -->
      <button
        class="bp-back-btn absolute left-5 top-5 z-[3] flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-white/[0.15] text-white transition-all duration-150 ease-out hover:bg-[var(--ray-surface)] hover:text-[var(--ray-text)]"
        onclick={goBack}
        aria-label={t('bot_preview.back', lang)}
        type="button"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><polyline points="15 18 9 12 15 6"></polyline></svg
        >
      </button>

      <div class="absolute inset-x-12 bottom-8 z-[2]">
        <div class="mb-3 flex flex-wrap items-center gap-1.5">
          {#each bot.categories as cat (cat)}
            <span
              class="rounded-full border border-white/[0.08] bg-[color-mix(in_srgb,var(--ray-surface)_70%,transparent)] px-3 py-[3px] font-[Maple_Mono,system-ui,sans-serif] text-[11px] font-medium tracking-[0.3px] text-[var(--ray-text)] backdrop-blur-[8px]"
            >
              {cat}
            </span>
          {/each}
          <span
            class="rounded-full border border-white/[0.08] bg-[color-mix(in_srgb,var(--ray-surface)_70%,transparent)] px-3 py-[3px] font-[Maple_Mono,system-ui,sans-serif] text-[10px] font-semibold uppercase tracking-[0.3px] backdrop-blur-[8px] {typeBadge.toneClass}"
          >
            {typeBadge.label}
          </span>
        </div>
        <h1
          class="m-0 font-[Maple_Mono,system-ui,sans-serif] text-[32px] font-semibold tracking-[0.2px] text-white"
          style="text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);"
        >
          {bot.name}
        </h1>
      </div>
    </div>

    <!-- ─── Two-column content ──────────────────────────────── -->
    <div class="bp-layout mx-auto grid max-w-[960px] grid-cols-[1fr_260px] items-start gap-8 px-12 pt-8 pb-6">
      <!-- Left column -->
      <div class="flex min-w-0 flex-col gap-4">
        <!-- Description -->
        {#if bot.description}
          <div
            class="bp-card rounded-xl border border-[var(--ray-border-card)] bg-[var(--ray-surface)] p-5"
          >
            <p
              class="m-0 whitespace-pre-wrap font-[Maple_Mono,system-ui,sans-serif] text-[14px] leading-[1.7] tracking-[0.2px] text-[var(--ray-text)]"
            >
              {bot.description}
            </p>
          </div>
        {/if}

        <!--
          Import error banner. Shown above Start Chat so the user
          sees the failure immediately after the popup-triggered
          import. The popup itself just kicks off the file picker
          and clears the error — the banner is the visual
          acknowledgement that something went wrong.
        -->
        {#if importError}
          <div
            class="rounded-lg border border-[color-mix(in_srgb,var(--ray-red)_30%,transparent)] bg-[color-mix(in_srgb,var(--ray-red)_10%,transparent)] px-4 py-2.5 text-center font-[Maple_Mono,system-ui,sans-serif] text-[12px] tracking-[0.2px] text-[var(--ray-red)]"
            role="alert"
          >
            {importError}
          </div>
        {/if}

        <!-- Start Chat — primary CTA -->
        <button
          class="bp-start-btn inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-full border-none px-7 py-3.5 font-[Maple_Mono,system-ui,sans-serif] text-[15px] font-semibold tracking-[0.3px] transition-opacity duration-150 ease-out hover:opacity-85"
          style="background: color-mix(in srgb, var(--ray-text) 90%, transparent); color: var(--ray-bg);"
          onclick={() => (showPersonaModal = true)}
          type="button"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            ><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path></svg
          >
          {t('bot_preview.start_chat', lang)}
        </button>

        <!--
          Edit Bot + Import Chat moved to the hero actions popup
          (top-right ⋯ button) — see "Hero actions" comment
          above. The hidden file input stays here so the popup
          action can trigger it via the startImport() handler.
        -->
        <input
          type="file"
          accept=".json"
          class="hidden"
          bind:this={fileInput}
          onchange={onFilePicked}
        />
      </div>

      <!-- Right column — poster -->
      <div class="bp-right sticky top-6">
        <div
          class="bp-poster overflow-hidden rounded-[14px] transition-transform duration-300 ease-in-out hover:scale-[1.04]"
        >
          {#if bot.avatar_path}
            <img
              src={avatarUrl(bot.avatar_path)}
              alt={bot.name}
              class="block aspect-[3/4] w-full object-cover"
            />
          {:else}
            <div
              class="flex aspect-[3/4] w-full items-center justify-center bg-gradient-to-br from-[#8b5cf6] to-[#06b6d4] text-[72px] font-bold text-white"
            >
              {bot.name.charAt(0).toUpperCase()}
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!--
      Recent chats — full-width section below the hero. Lives
      OUTSIDE the .bp-layout grid so the threads tree can use
      the full 960px width when there are long fork chains.
    -->
    <section class="mx-auto max-w-[960px] px-12 pb-12">
      <div class="mb-3 flex items-baseline justify-between">
        <h2
          class="m-0 font-[Maple_Mono,system-ui,sans-serif] text-[12px] font-semibold uppercase tracking-[0.5px] text-[var(--ray-text-tertiary)]"
        >
          {t('chat.tree.title', lang)}
        </h2>
        {#if recentThreads.length > 0}
          <span
            class="font-[Maple_Mono,system-ui,sans-serif] text-[11px] tabular-nums tracking-[0.2px] text-[var(--ray-text-tertiary)]"
            aria-label={t('chat.tree.total_count_aria', lang, { n: recentThreads.length })}
          >
            {t('chat.tree.total_count', lang, { n: recentThreads.length })}
          </span>
        {/if}
      </div>
      <div
        class="rounded-xl border border-[var(--ray-border-card)] bg-[color-mix(in_srgb,var(--ray-surface)_50%,transparent)] p-2"
      >
        <ThreadTree
          threads={recentThreads}
          botAvatarPath={bot.avatar_path}
          onselectThread={(_, threadId) => openThread(threadId)}
          botId={bot?.id ?? 0}
          {lang}
        />
      </div>
    </section>
  {/if}
</div>

<PersonaSelectModal
  show={showPersonaModal}
  {personas}
  botId={bot?.id ?? 0}
  {lang}
  mode={importing ? 'import' : 'chat'}
  onselect={importing ? onImportPersonaSelected : onNewThread}
  onclose={() => {
    showPersonaModal = false;
    importing = false;
  }}
/>

<style>
  /* ── Pieces Tailwind can't reasonably express ───────────────
     The hero overlay is a vertical gradient (3-stop fade) that
     gives the bot name legibility against any avatar — pure
     linear-gradient with a custom angle. The Raycast double-ring
     shadow on .bp-card is a 2-layer box-shadow that the design
     system explicitly encodes (see DESIGN.md "Elevation &
     Depth"). The poster shadow is the same double-ring plus a
     generous drop shadow.
     Everything else lives in the template as Tailwind utilities. */

  .bp-hero {
    background: color-mix(in srgb, var(--ray-text) 3%, transparent);
  }
  .bp-hero-overlay {
    background: linear-gradient(
      to top,
      var(--ray-bg, #07080a) 15%,
      transparent
    );
  }

  /* Raycast double-ring on description card. */
  .bp-card {
    box-shadow:
      var(--ray-shadow-ring, rgba(0, 0, 0, 0.04)) 0px 0px 0px 1px,
      var(--ray-shadow-inset, rgba(0, 0, 0, 0.02)) 0px 0px 0px 1px inset;
  }

  /* Poster has the double-ring PLUS a soft drop shadow — it
     needs to feel like a physical card sitting on the page. */
  .bp-poster {
    box-shadow:
      var(--ray-shadow-ring, rgba(0, 0, 0, 0.04)) 0px 0px 0px 1px,
      0 8px 32px rgba(0, 0, 0, 0.2);
  }

  /* ── Responsive ─────────────────────────────────────────── */
  @media (max-width: 768px) {
    .bp-hero {
      height: 200px;
    }
    .bp-hero h1 {
      font-size: 24px;
    }
    .bp-hero > div:last-child {
      left: 20px;
      right: 20px;
      bottom: 20px;
    }
    .bp-layout {
      grid-template-columns: 1fr;
      padding: 20px 16px 24px;
      gap: 20px;
    }
    .bp-right {
      display: none;
    }
    section {
      padding-left: 16px;
      padding-right: 16px;
      padding-bottom: 32px;
    }
  }

  /* ── Hero actions popover ───────────────────────────────────
     Glass overlay anchored to the top-right ⋯ button. Uses
     the same visual shell as ChatHeader.ch-menu — backdrop-
     blur + 1px border + soft drop shadow — so the user sees a
     consistent popover family across the app.

     ``.bp-actions-btn--open`` keeps the trigger visually
     distinct while the popup is mounted (matches the
     ChatHeader.ch-btn.active pattern). */
  .bp-actions-btn--open {
    background: var(--ray-surface);
    color: var(--ray-text);
  }
  .bp-actions-popup {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 200px;
    padding: 4px;
    background: color-mix(in srgb, var(--ray-surface) 92%, transparent);
    border: 1px solid var(--ray-border-strong);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .bp-actions-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: none;
    background: transparent;
    color: var(--ray-text);
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s ease;
    white-space: nowrap;
  }
  .bp-actions-item:hover {
    background: color-mix(in srgb, var(--ray-text) 5%, transparent);
  }
</style>
