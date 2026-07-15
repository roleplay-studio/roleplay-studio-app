<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';

  import {
    api,
    apiBase,
    type Bot,
    type LLMDebugInfo,
    type LLMUsage,
    type Message,
    type Persona,
    type RecentThread,
    type Thread,
    type ThreadFileDTO,
    type ThreadStats,
  } from '../api';
  import { ttsApi, TTSDisabledError } from '../api';
  import ChatHeader from '../ChatHeader.svelte';
  import ChatInput from '../ChatInput.svelte';
  import { getAutoplayTts } from '../chatSettings';
  import DeleteConfirmModal from '../DeleteConfirmModal.svelte';
  import EditMessageModal from '../EditMessageModal.svelte';
  import { currentLang, t } from '../i18n';
  import LLMDebugModal from '../LLMDebugModal.svelte';
  import MessageBubble from '../MessageBubble.svelte';
  import PersonaSelectModal from '../PersonaSelectModal.svelte';
  import RecentChats from '../RecentChats.svelte';
  import ThreadDrawer from '../ThreadDrawer.svelte';
  import Loading from '../ui/Loading.svelte';
  import NotificationModal from '../ui/NotificationModal.svelte';
  import { displayedMessages, isGreetingLocked } from '../utils/chat-greetings';
  import { syncVersionsStateFromMessages } from '../utils/chat-versions';
  import { attachInfiniteScroll } from '../utils/infiniteScrollSentinel';
  import { dismissNotification, isNotificationDismissed } from '../utils/notificationStore';
  import { parseMessageContent } from '../utils/parseMetadata';
  import { captureScrollAnchor, restoreScrollAnchor } from '../utils/scrollAnchor';

  // Dev-mode gate for the LLM debug modal. Vite's import.meta.env.DEV
  // is true for `npm run dev` and `tauri dev`, false for production
  // builds. We never expose the modal in production even if the
  // backend accidentally shipped a debug event.
  const DEV_MODE = import.meta.env.DEV;

  // Props
  const {
    botId: botIdParam = '0',
    personaId: personaIdParam = null,
    threadId: threadIdParam = null,
  }: { botId?: string; personaId?: null | string; threadId?: null | string } = $props();

  // State
  let bot: Bot | null = $state(null);
  let threads: Thread[] = $state([]);
  let messages: Message[] = $state([]);

  // Greeting switcher state.
  // The switcher is locked only once the user has sent a message —
  // the auto-saved first_message assistant bubble (persisted by
  // ChatService._build_request) does NOT lock the switcher, because
  // the user is still deciding whether to engage.
  let selectedGreetingIndex = $state(0);
  let greetingLocked = $derived(isGreetingLocked(messages));
  let availableGreetings = $derived.by(() => {
    if (!bot) return [] as string[];
    const list = [bot.first_message, ...(bot.alternate_greetings ?? [])]
      .map((s: string) => s.trim())
      .filter(Boolean);
    return list;
  });
  // Holds the currently-selected greeting text. Used by the sendMessage
  // handler to persist the chosen greeting to the DB on the first user
  // send (Task 3 of greeting plan).
  let currentGreeting = $derived(availableGreetings[selectedGreetingIndex] ?? '');
  // Render the message array with the currently-selected greeting overlaid
  // onto the first assistant bubble — but only until the user has spoken.
  // After the first user send, displayedMessages() short-circuits and
  // returns the messages as-is, so the bubble shows the persisted greeting.
  let displayedMessagesView = $derived(
    displayedMessages(messages, availableGreetings, selectedGreetingIndex),
  );
  let selectedThreadId: null | number = $state(null);
  const selectedBotId = $derived(parseInt(botIdParam) || 0);
  let loading = $state(true);
  let streaming = $state(false);
  // AbortController for the current /messages fetch. Lets us close the
  // SSE stream client-side when the user hits Stop, and is also passed
  // to /abort as the server-side kill signal.
  let streamAbort: AbortController | null = null;
  let streamError = $state(false);
  // Current <audio> for the autoplay-TTS feature. Not $state — we
  // don't want the chat to re-render every time playback state ticks;
  // the per-message TTSButton has its own audio element so it can
  // keep working even if autoplay is mid-flight. ``null`` when idle.
  let autoplayAudio: HTMLAudioElement | null = null;
  // The message id we're autoplaying. We only autoplay the freshly
  // persisted assistant message from the stream that just ended; on
  // thread switch / new send we drop the old id so a stale "still
  // listening to the previous reply" doesn't trigger twice.
  let autoplayTargetId: null | number = null;
  let messagesEnd: HTMLDivElement | undefined = $state();
  // Scrollable messages container — used to detect when the user has
  // scrolled up so the "jump to bottom" button can appear.
  let chatScroll: HTMLDivElement | undefined = $state();
  // Invisible sentinel element placed at the top of the message list.
  // When it scrolls within `rootMargin` of the viewport, the attached
  // IntersectionObserver fires `loadMoreOlder()`. We use this instead
  // of an onscroll handler so the browser debounces for us and we
  // don't fire on every wheel tick.
  let loadMoreSentinel: HTMLDivElement | undefined = $state();
  // True when the user has scrolled away from the bottom of the message
  // list. Threshold (64px) avoids flicker on rubber-band and on small
  // rounding errors from `scrollIntoView` smooth scrolling.
  let showJumpToBottom = $state(false);

  // ── Lazy history loading ─────────────────────────────────────────
  // Long chats (DEBUG1 has 114+ messages) used to be silently truncated
  // at 50 because the API client hard-coded a `limit=50` default. We
  // now fetch the newest page on thread open and let the user pull
  // older pages on demand via a "Load older" button.
  const MESSAGE_PAGE_SIZE = 50;
  let loadingMore = $state(false);
  // False once the server returns a short page — no point asking again.
  let hasMoreOlder = $state(false);
  // The smallest message id currently rendered. Used as the keyset
  // cursor for the next "load older" request. The backend returns
  // messages oldest → newest, so index 0 is the oldest.
  let oldestRenderedId: null | number = $derived.by(() => {
    for (const m of messages) {
      if (m.id != null) return m.id;
    }
    return null;
  });

  function handleChatScroll() {
    if (!chatScroll) return;
    const { clientHeight, scrollHeight, scrollTop } = chatScroll;
    showJumpToBottom = scrollTop + clientHeight < scrollHeight - 64;
  }

  // Persona
  let personas: Persona[] = $state([]);
  let selectedPersonaId: null | number = $state(null);

  // Thread drawer
  let showThreadDrawer = $state(false);

  // Cross-bot recent chats (no bot selected — fallback view).
  let lang = $state('en');
  let crossBotThreads: RecentThread[] = $state([]);
  let unsubLang: (() => void) | undefined;

  // Persona select modal for new thread
  let showPersonaModal = $state(false);

  // Edit modal
  let showEditModal = $state(false);
  let editMessageId: null | number = $state(null);
  let editContent = $state('');
  // World-state snapshot for the assistant message being edited.
  // ``null`` means "the message has no state column populated yet,
  // hide the second textarea" — only assistant turns ever carry a
  // state. The local ``editMessageState`` mirror handles the typed
  // value; on save we send a string (including ``""`` for "clear
  // the snapshot") so the server can distinguish clearing from
  // "use the original message's state" via the explicit-null vs
  // omitted-state route contract.
  let editMessageState: null | string = $state(null);

  // Delete confirm
  let showDeleteConfirm = $state(false);
  let deletingMsgId = $state<null | number>(null);

  // Notification modal
  let notificationMessage = $state<null | string>(null);

  // Context compression
  let compressing = $state(false);
  let hasSummary = $state(false);

  // Stats
  // ``messageCount`` / ``totalTokens`` are kept for the *rendered*
  // page (e.g. the scroll-virtualizer, the token-aware LLM debug
  // modal), but the chat header binds to ``realMessageCount`` /
  // ``realTokenEstimate`` — the values from the dedicated
  // ``GET /api/threads/{id}/stats`` endpoint that reflect the FULL
  // thread, not just the latest 50-message page. Deriving header
  // counts from ``messages.length`` was the 0.0.4 bug: visually
  // capped at 50 even on threads with hundreds of exchanges.
  const messageCount = $derived(messages.filter((m) => m.role !== 'system').length);
  const totalTokens = $derived(
    messages.reduce((sum, m) => sum + (m.content ? Math.ceil(m.content.length / 4) : 0), 0),
  );
  let threadStats: null | ThreadStats = $state<null | ThreadStats>(null);
  const realMessageCount = $derived(threadStats?.message_count ?? messageCount);
  const realTokenEstimate = $derived(threadStats?.token_estimate ?? totalTokens);

  // File attachments
  let messageFiles: Record<number, ThreadFileDTO[]> = $state({});

  // Dev-mode LLM debug state. Populated from the `usage` and `debug`
  // SSE events emitted by the backend (only when Settings.debug_enabled
  // is true on the server). The Maps are keyed by the assistant
  // message's eventual DB id — we patch the entry once the message
  // gets an id from the post-stream listMessages refresh.
  let debugByMessage: Record<number, LLMDebugInfo> = $state({});
  let usageByMessage: Record<number, LLMUsage> = $state({});
  // Modal state. Null = closed. The id is the assistant message whose
  // payload we want to display.
  let openDebugId: null | number = $state(null);
  function openDebugModal(msgId: number) {
    if (DEV_MODE && debugByMessage[msgId]) {
      openDebugId = msgId;
    }
  }
  function closeDebugModal() {
    openDebugId = null;
  }
  // Pending (pre-DB-id) debug payload — collected during a stream and
  // attached to the assistant message once the post-stream refresh
  // resolves its real id. The orchestrator yields the debug event at
  // the head of the stream, but at that point the assistant bubble
  // has no id yet (it only gets one from the server's response).
  let pendingDebug: LLMDebugInfo | null = $state(null);
  let pendingUsage: LLMUsage | null = $state(null);

  // Branching / versions
  let versions: Record<number, Message[]> = $state({});
  let versionsCount: Record<number, number> = $state({});
  let currentVersionIndex: Record<number, number> = $state({});

  // Init
  let initialLoad = $state(true);

  onMount(async () => {
    unsubLang = currentLang.subscribe((v) => (lang = v));
    await loadPersonas();
    if (selectedBotId) {
      await loadBot(selectedBotId);
    } else {
      // No bot selected — show the cross-bot recent chats list.
      // Forks are a same-bot relationship so a tree wouldn't make
      // sense here; RecentChats keeps the original UX for this view.
      try {
        crossBotThreads = await api.listRecentThreads();
      } catch (e) {
        console.error('Failed to load recent threads:', e);
      }
      loading = false;
    }
    initialLoad = false;
  });

  $effect(() => {
    if (initialLoad) return;
    if (selectedBotId) {
      bot = null;
      threads = [];
      messages = [];
      // Drop any in-flight autoplay from the previous bot — the
      // chat-window settings popover is the only piece of UI the
      // user expects to survive a bot switch.
      stopAutoplay();
      selectedThreadId = null;
      editMessageId = null;
      editContent = '';
      // Reset the dedicated stats binding too — the page-local
      // ``messages.length`` fallback won't surface the real total
      // until the next ``refreshThreadStats`` resolves, but at least
      // the header won't show a stale number from the previous
      // bot's thread.
      threadStats = null;
      loading = true;
      loadBot(selectedBotId);
    } else {
      // Switching FROM a bot TO the no-bot fallback view. Drop the
      // per-bot state so the chat page leaves cleanly. crossBotThreads
      // is NOT reset here — it gets refetched on the next mount via
      // listRecentThreads().
      bot = null;
      threads = [];
      messages = [];
      stopAutoplay();
      selectedThreadId = null;
      threadStats = null;
      loading = false;
    }
  });

  // Lazy-load hook: attach an IntersectionObserver to the top-of-list
  // sentinel whenever both the scroll container and the sentinel ref
  // are bound. The observer fires `loadMoreOlder()` while the user
  // scrolls toward the top, and tears itself down on dispose or when
  // either ref is rebound. ``hasMoreOlder`` is also a reactive dep so
  // a successful end-of-list fetch removes the observer automatically.
  $effect(() => {
    if (!loadMoreSentinel || !chatScroll) return;
    if (!hasMoreOlder) return;
    // The helper returns a disconnect fn; Svelte invokes it on cleanup
    // and on every dependency change.
    return attachInfiniteScroll(loadMoreSentinel, () => loadMoreOlder(), {
      root: chatScroll,
      rootMargin: '200px 0px',
    });
  });

  onDestroy(() => {
    unsubLang?.();
    stopAutoplay();
  });

  // ── Data loading ──

  async function loadPersonas() {
    try {
      personas = await api.listPersonas();
      if (personaIdParam) {
        const pid = parseInt(personaIdParam);
        if (pid && personas.some((p) => p.id === pid)) selectedPersonaId = pid;
      }
    } catch (e) {
      console.error('Failed to load personas:', e);
    }
  }

  async function loadBot(id: number) {
    try {
      bot = await api.getBot(id);
      threads = await api.listBotThreads(id);
      // If threadId specified, select it; otherwise auto-select first
      const targetThread = threadIdParam
        ? threads.find((t) => t.id === parseInt(threadIdParam))
        : null;
      if (targetThread) {
        selectThread(targetThread.id);
      } else if (threads.length > 0) {
        selectThread(threads[0].id);
      } else {
        const newThread = await api.createThread(id);
        selectThread(newThread.id);
      }
    } catch (e) {
      console.error('Failed to load bot', e);
    } finally {
      loading = false;
    }
  }

  async function selectThread(threadId: number) {
    selectedThreadId = threadId;
    messages = await api.listMessages(threadId, MESSAGE_PAGE_SIZE);
    // If the first page is full there might be older messages; show the
    // "load older" affordance. A short page means we've got everything
    // in one shot — DEBUG1-style chats will see the button, short
    // conversations will not.
    hasMoreOlder = messages.length >= MESSAGE_PAGE_SIZE;
    // Load files for all messages in one request
    await loadThreadFiles(threadId);
    // Load real header stats. Run in parallel with file/version setup
    // so the page transition feels snappy — if the call fails (e.g.
    // user race-cleared the thread) we silently keep the page-local
    // fallback values derived from ``messages.length``.
    void refreshThreadStats(threadId);
    // Sync versions state from the embedded msg.versions field that
    // the backend already populates in listMessages.
    const synced = syncVersionsStateFromMessages(messages);
    versions = { ...versions, ...synced.versions };
    currentVersionIndex = { ...currentVersionIndex, ...synced.currentVersionIndex };
    // Restore persona from thread
    const thread = threads.find((t) => t.id === threadId);
    if (thread) selectedPersonaId = thread.persona_id;
    // Check for notification in last assistant message (from server-load)
    const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
    if (lastAssistant?.content) {
      const parsed = parseMessageContent(lastAssistant.content);
      if (parsed.notification && !isNotificationDismissed(parsed.notification)) {
        notificationMessage = parsed.notification;
      }
    }
    checkSummary(threadId);
    // `force=true` here: this is the *initial* load, not a streaming
    // chunk — the user always expects to land on the latest message,
    // not wherever the previous scroll position happened to be.
    scrollToBottom(true);
  }

  /** Fetch the full-thread header stats (independent of pagination).
   *
   * Called when entering a thread, and again whenever the page-local
   * ``messages.length`` flips relative to the last known stats — that
   * catches the case where the user just sent a new turn (count
   * should bump) without paying for a network call on every render.
   */
  async function refreshThreadStats(threadId: number): Promise<void> {
    try {
      threadStats = await api.getThreadStats(threadId);
    } catch (e) {
      // 404 (thread gone) or network blip: leave the page-local
      // ``messages.length``-derived fallback in place. The header
      // will at worst show a slightly-stale count rather than 0.
      console.debug('getThreadStats failed; using local fallback', e);
    }
  }

  async function loadThreadFiles(threadId: number) {
    try {
      const allFiles = await api.listThreadFiles(threadId);
      const grouped: Record<number, ThreadFileDTO[]> = {};
      for (const f of allFiles) {
        if (f.message_id != null) {
          if (!grouped[f.message_id]) grouped[f.message_id] = [];
          grouped[f.message_id].push(f);
        }
      }
      messageFiles = grouped;
    } catch {
      /* ignore */
    }
  }

  // Fetch the next older page of messages and prepend it to the list.
  // The scroll position is preserved by measuring the container's
  // height before/after the prepend and applying the delta — without
  // this, the user would get yanked to the top on every click.
  //
  // Returns ``true`` when more pages might still exist, ``false`` when
  // the server returned a short page (end of history). The result
  // drives the IntersectionObserver lifecycle: returning ``false``
  // causes ``attachInfiniteScroll`` to disconnect itself.
  async function loadMoreOlder(): Promise<boolean> {
    if (!selectedThreadId || !hasMoreOlder || loadingMore) return false;
    if (oldestRenderedId == null) {
      hasMoreOlder = false;
      return false;
    }
    loadingMore = true;
    // ── Anchor-based scroll preservation ──
    // The classic "measure scrollHeight before/after, then add the
    // delta to scrollTop" approach is fragile when the inserted
    // content uses `content-visibility: auto` + `contain-intrinsic-
    // size`: at the moment we measure `afterHeight`, the browser may
    // not have finished resolving the placeholder sizes into the
    // real heights, so the delta is *underestimated* and the user's
    // view jumps by however many pixels the placeholders shrank.
    //
    // Instead we anchor on the *first visible message*. We capture
    // its id and the offset of its top edge from the top of the
    // scroll container *before* the prepend. After the prepend, we
    // find that same message (now further down in the list) and set
    // scrollTop so its top edge sits at the same offset.
    //
    // This is immune to layout shifts from content-visibility, image
    // loads, font swap, etc. — whatever happens to the heights of
    // the freshly-prepended bubbles, the anchor message stays
    // exactly where it was.
    const scrollEl = chatScroll;
    const snapshot = captureScrollAnchor(scrollEl);
    try {
      const older = await api.listMessages(selectedThreadId, MESSAGE_PAGE_SIZE, oldestRenderedId);
      if (older.length === 0) {
        hasMoreOlder = false;
        return false;
      }
      // Deduplicate by id in case a race re-inserts the boundary message.
      const knownIds = new Set(messages.map((m) => m.id).filter((x) => x != null));
      const fresh = older.filter((m) => m.id == null || !knownIds.has(m.id));
      messages = [...fresh, ...messages];
      // A short page means we've reached the bottom of history.
      if (older.length < MESSAGE_PAGE_SIZE) {
        hasMoreOlder = false;
        return false;
      }
      // Restore scroll position so the anchor message sits at the same
      // visible offset. We use a *double* rAF:
      //   - First rAF: Svelte has flushed, the new MessageBubble
      //     nodes are in the DOM and have their initial placeholder
      //     size.
      //   - Second rAF: the browser has actually laid out the new
      //     bubbles — even with content-visibility:auto, the ones
      //     we just inserted near the top are now in the visible
      //     region and have been measured.
      // We resolve the anchor element *after* the second rAF so we
      // measure the real (post-layout) position, not the pre-layout
      // placeholder.
      if (snapshot.anchorId != null && snapshot.anchorOffset != null) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            restoreScrollAnchor(scrollEl, snapshot);
          });
        });
      }
    } catch (e) {
      console.error('Failed to load older messages', e);
      return false;
    } finally {
      loadingMore = false;
    }
    return true;
  }

  async function newThread() {
    if (!selectedBotId) return;
    // Show persona selection modal instead of creating directly
    showPersonaModal = true;
  }

  async function onNewThreadWithPersona(threadId: number) {
    showPersonaModal = false;
    try {
      threads = await api.listBotThreads(selectedBotId);
      const newThread = threads.find((t) => t.id === threadId);
      if (newThread) selectThread(threadId);
    } catch (e) {
      console.error('Failed to refresh threads:', e);
    }
  }

  async function deleteCurrentThread() {
    if (!selectedThreadId) return;
    await api.deleteThread(selectedThreadId);
    threads = threads.filter((t) => t.id !== selectedThreadId);
    if (threads.length > 0) {
      selectThread(threads[0].id);
    } else {
      selectedThreadId = null;
      messages = [];
    }
  }

  // ── Chat ──

  async function stopStreaming() {
    if (!streaming) return;
    // 1) Close the client-side SSE stream immediately (fast feedback).
    if (streamAbort) {
      streamAbort.abort();
      streamAbort = null;
    }
    // 2) Fire-and-forget the server-side abort so the LLM task is killed
    //    even if the SSE connection lingers. Best-effort — log on error
    //    but don't block the UI.
    if (selectedThreadId) {
      try {
        await api.abortGeneration(selectedThreadId);
      } catch (e) {
        console.error('abort endpoint failed', e);
      }
    }
    streaming = false;
    // The stream-loop's `except CancelledError` branch has already saved
    // the partial assistant message. The fetch() above will reject on
    // abort, which the catch-block in sendMessage already handles by
    // setting streaming=false and not showing a network error. No further
    // UI work is needed here.
  }

  function stopAutoplay() {
    if (autoplayAudio) {
      autoplayAudio.pause();
      autoplayAudio = null;
    }
    autoplayTargetId = null;
  }

  /**
   * Auto-play the most recent assistant message via TTS. Called from
   * the two stream-finished sites (send + regenerate). Honours the
   * ``autoplayTts`` user preference and silently bails out on every
   * known failure mode (TTS disabled server-side, network error,
   * autoplay-blocked by the browser) — autoplay is a convenience,
   * not a contract.
   *
   * Stripping markdown / metadata via parseMessageContent keeps the
   * speech clean — same approach TTSButton uses for its inline play.
   */
  async function autoPlayLastAssistant() {
    if (!getAutoplayTts()) return;
    if (!messages.length) return;
    const last = messages[messages.length - 1];
    if (last.role !== 'assistant' || last.id == null) return;
    // Already playing this exact message? No-op. (regen can call us
    // twice if both branches trigger.)
    if (autoplayTargetId === last.id && autoplayAudio) return;
    // Only autoplay when there's actual text to speak. Don't shout
    // greeting placeholders, world-state blocks, or error messages.
    const parsed = parseMessageContent(last.content);
    const text = parsed.mainContent.trim();
    if (!text) return;
    stopAutoplay();
    autoplayTargetId = last.id;
    let cacheId: string;
    try {
      const resp = await ttsApi.synthesize({ text });
      cacheId = resp.cache_id;
    } catch (err) {
      if (err instanceof TTSDisabledError) {
        // Server told us TTS is off — clear the autoplay target so
        // we don't keep trying on every subsequent message. The
        // per-message TTSButton also hides itself via sessionStorage
        // (see TTSButton.svelte).
        autoplayTargetId = null;
        return;
      }
      console.warn('Autoplay TTS: synthesize failed', err);
      autoplayTargetId = null;
      return;
    }
    const audio = new Audio(ttsApi.audioUrl(cacheId));
    autoplayAudio = audio;
    audio.onended = () => {
      // Only null out if we're still on this audio element — a new
      // autoplay might have replaced it in the meantime.
      if (autoplayAudio === audio) {
        autoplayAudio = null;
        autoplayTargetId = null;
      }
    };
    audio.onerror = () => {
      if (autoplayAudio === audio) {
        autoplayAudio = null;
        autoplayTargetId = null;
      }
    };
    try {
      await audio.play();
    } catch (err) {
      // Browsers reject .play() outside a user gesture the first
      // time; the most likely cause here is the user toggled autoplay
      // on via the gear icon (which IS a user gesture), but on some
      // browsers strict autoplay policies still kick in. Just give up
      // quietly — the user can hit the per-message ▶ button.
      console.warn('Autoplay TTS: play() rejected', err);
      if (autoplayAudio === audio) {
        autoplayAudio = null;
        autoplayTargetId = null;
      }
    }
  }

  async function sendMessage(text: string, fileIds: number[] = []) {
    if (!selectedThreadId || !selectedBotId) return;

    // Persist the selected greeting BEFORE the first user send.
    // The auto-saved first_message (line 1 of messages) is what the user
    // will read when they reload the thread. If they picked an alternate
    // greeting via the switcher, we materialise that choice in the DB
    // here so the choice survives a page refresh.
    const firstUserSend = !messages.some((m) => m.role === 'user');
    if (firstUserSend && messages.length > 0 && messages[0].id !== null) {
      if (currentGreeting && currentGreeting !== messages[0].content) {
        await api.updateMessage(selectedThreadId, messages[0].id!, currentGreeting);
        // Reflect the change locally so subsequent operations
        // (e.g. listMessages on refresh) see the new content.
        messages = [{ ...messages[0], content: currentGreeting }, ...messages.slice(1)];
      }
    }

    // Normalize: if empty/whitespace-only, send *continue* to keep pushing the story
    const content = text.trim() || '*continue*';
    messages = [
      ...messages,
      {
        branch_group: null,
        branch_index: 0,
        content: content,
        created_at: null,
        id: null,
        is_active: true,
        role: 'user',
        short_content: '',
      },
    ];
    scrollToBottom();
    streaming = true;
    streamError = false;
    let gotError = false;

    // Create a fresh AbortController so Stop can close the SSE stream
    // and so /abort can find the request to kill.
    streamAbort = new AbortController();
    // Use the reactive `apiBase()` (reads localStorage.serverUrl on
    // every call) rather than the module-captured `API_BASE` constant
    // — `API_BASE` freezes the URL at module load, so a user who
    // pointed the client at a remote server via localStorage still
    // hits the original localhost endpoint after the change.
    const messageUrl = `${apiBase()}/api/threads/${selectedThreadId}/messages`;
    try {
      const resp = await fetch(messageUrl, {
        body: JSON.stringify({
          bot_id: selectedBotId,
          file_ids: fileIds,
          persona_id: selectedPersonaId,
          user_input: content,
        }),
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
        signal: streamAbort.signal,
      });
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
          const body = await resp.json();
          detail = body.detail || detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('No reader');

      messages = [
        ...messages,
        {
          branch_group: null,
          branch_index: 0,
          content: '',
          created_at: null,
          id: null,
          is_active: true,
          reasoning: '',
          role: 'assistant',
          short_content: '',
        },
      ];
      let buffer = '';
      let assistantContent = '';
      let assistantReasoning = '';

      // Reset pending debug/usage — the orchestrator always yields the
      // debug event as the FIRST chunk, so any prior state from a
      // previous stream is stale.
      pendingDebug = null;
      pendingUsage = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += new TextDecoder().decode(value);
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') {
              assistantContent += data.content;
              messages[messages.length - 1] = {
                branch_group: null,
                branch_index: 0,
                content: assistantContent,
                created_at: null,
                id: null,
                is_active: true,
                reasoning: assistantReasoning || undefined,
                role: 'assistant',
                short_content: '',
              };
              scrollToBottom();
            } else if (data.type === 'reasoning') {
              // Reasoning tokens are kept in component state only — the
              // backend never persists them. They're rendered in a
              // collapsible "Reasoning" panel under the message.
              assistantReasoning += data.content;
              messages[messages.length - 1] = {
                ...messages[messages.length - 1],
                reasoning: assistantReasoning,
              };
            } else if (data.type === 'usage') {
              // Dev-mode token counts. Stashed on the pending entry —
              // we don't know the assistant message's DB id yet, so
              // the post-stream listMessages refresh will re-attach
              // it to the persisted id.
              pendingUsage = data.usage as LLMUsage;
            } else if (data.type === 'debug') {
              // Dev-mode full request payload. Same lifecycle as usage.
              pendingDebug = data.debug as LLMDebugInfo;
            } else if (data.type === 'error') {
              gotError = true;
              streamError = true;
              // Remove the empty assistant bubble
              messages = messages.slice(0, -1);
              // Add error message
              messages = [
                ...messages,
                {
                  branch_group: null,
                  branch_index: 0,
                  content: `⚠️ ${data.detail || 'Failed to generate response'}`,
                  created_at: null,
                  id: null,
                  is_active: true,
                  role: 'assistant',
                  short_content: '',
                },
              ];
              scrollToBottom();
              console.error('Stream error:', data.detail);
            } else if (data.type === 'done') {
              // Stream completed successfully
            }
          } catch {
            /* ignore */
          }
        }
      }

      // Check for notification after streaming completes
      if (assistantContent) {
        const parsed = parseMessageContent(assistantContent);
        if (parsed.notification && !isNotificationDismissed(parsed.notification)) {
          notificationMessage = parsed.notification;
        }
      }
    } catch (e) {
      console.error('Send failed:', e);
      streamError = true;
      if (typeof gotError === 'undefined' || !gotError) {
        // Wrap fetch's opaque network error so the user sees which URL
        // was hit. A bare "Error: TypeError: Failed to fetch" hides
        // whether the client was pointed at the wrong host, the port
        // is closed, or the server crashed mid-request.
        const detail =
          e instanceof TypeError && /fetch/i.test(e.message)
            ? `Connection refused — backend not reachable at ${messageUrl}`
            : e instanceof Error
              ? e.message
              : String(e);
        messages = [
          ...messages,
          {
            branch_group: null,
            branch_index: 0,
            content: `⚠️ ${detail}`,
            created_at: null,
            id: null,
            is_active: true,
            role: 'assistant',
            short_content: '',
          },
        ];
      }
    } finally {
      streaming = false;
      scrollToBottom();
      // Only refresh from server if no error occurred — keeps error message visible
      if (!streamError && selectedThreadId) {
        const tid = selectedThreadId;
        api
          .listMessages(tid)
          .then((msgs) => {
            messages = msgs;
            // Keep the chat-header stats in lockstep with the freshly-
            // persisted message counts (assistant + reasoning rows,
            // file-attachment rows, etc. all increase the chain).
            void refreshThreadStats(tid);
            // Re-attach the dev-mode debug/usage payload to the
            // assistant message's real DB id. The stream yielded
            // these events before the message was persisted, so we
            // couldn't store them under an id at the time. Find the
            // last assistant message in the refreshed list — that's
            // the one we just generated — and slot the payload in.
            if (pendingDebug || pendingUsage) {
              const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant');
              if (lastAssistant?.id != null) {
                if (pendingDebug) {
                  debugByMessage = { ...debugByMessage, [lastAssistant.id]: pendingDebug };
                }
                if (pendingUsage) {
                  usageByMessage = { ...usageByMessage, [lastAssistant.id]: pendingUsage };
                }
              }
              pendingDebug = null;
              pendingUsage = null;
            }
            // Autoplay hook: the message is now persisted with a real
            // id and full content, so it's the right time to TTS it.
            void autoPlayLastAssistant();
            scrollToBottom();
          })
          .catch(() => {});
      } else {
        // Stream errored — drop the pending debug info, the message
        // we appended to messages is an error placeholder, not the
        // real LLM response, so any debug data would be misleading.
        pendingDebug = null;
        pendingUsage = null;
      }
      // Refresh threads list to pick up auto-generated thread name
      if (selectedBotId) {
        api
          .listBotThreads(selectedBotId)
          .then((t) => (threads = t))
          .catch(() => {});
      }
    }
  }

  // ── Regeneration / Branching ──

  async function handleRegenerate(messageId: number) {
    if (!selectedThreadId || !selectedBotId || streaming) return;
    streaming = true;

    try {
      const resp = await api.regenerateMessage(
        selectedThreadId,
        messageId,
        selectedBotId,
        selectedPersonaId,
      );
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
          const body = await resp.json();
          detail = body.detail || detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('No reader');

      let buffer = '';
      let regenContent = '';
      let regenReasoning = '';
      // Reset pending debug/usage — same lifecycle as sendMessage.
      pendingDebug = null;
      pendingUsage = null;

      // Replace the last assistant message in the array — it's the one being regenerated
      // Find the index of the message with this id
      const msgIndex = messages.findIndex((m) => m.id === messageId);
      if (msgIndex === -1) throw new Error('Message not found');

      // Immediately clear content to show something is happening
      messages[msgIndex] = { ...messages[msgIndex], content: '', reasoning: '' };
      messages = messages;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += new TextDecoder().decode(value);
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') {
              regenContent += data.content;
              messages[msgIndex] = {
                ...messages[msgIndex],
                content: regenContent,
                reasoning: regenReasoning || undefined,
              };
              scrollToBottom();
            } else if (data.type === 'reasoning') {
              regenReasoning += data.content;
              messages[msgIndex] = { ...messages[msgIndex], reasoning: regenReasoning };
            } else if (data.type === 'usage') {
              pendingUsage = data.usage as LLMUsage;
            } else if (data.type === 'debug') {
              pendingDebug = data.debug as LLMDebugInfo;
            } else if (data.type === 'done') {
              console.log('REGEN DONE:', data);
              // Update the message with server response data
              if (data.message) {
                messages[msgIndex] = data.message as Message;
                messages = messages; // trigger reactivity
                // Autoplay hook: regen gives us the persisted id and
                // full content inline (no follow-up listMessages call),
                // so this is the symmetric counterpart to the
                // post-refresh hook in sendMessage.
                void autoPlayLastAssistant();
                // Re-attach dev-mode debug/usage to the new message id.
                // Regen is special: the done event hands us the new id
                // synchronously, so we don't need a post-stream refresh.
                const newId = data.message.id;
                if (newId != null) {
                  if (pendingDebug) {
                    debugByMessage = { ...debugByMessage, [newId]: pendingDebug };
                    pendingDebug = null;
                  }
                  if (pendingUsage) {
                    usageByMessage = { ...usageByMessage, [newId]: pendingUsage };
                    pendingUsage = null;
                  }
                }
              }
              // Store versions info — keyed by the NEW message ID
              if (data.versions) {
                const vers = data.versions as Message[];
                const newMsgId = data.message?.id ?? messageId;
                versions = { ...versions, [newMsgId]: vers };
                // Also keep under old ID for fallback
                if (newMsgId !== messageId) {
                  versions = { ...versions, [messageId]: vers };
                }
                versionsCount = { ...versionsCount, [newMsgId]: vers.length };
                const activeIdx = vers.findIndex((v) => v.is_active);
                currentVersionIndex = {
                  ...currentVersionIndex,
                  [newMsgId]: activeIdx >= 0 ? activeIdx : 0,
                };
              }
              // Fallback: re-fetch versions from server
              try {
                const resVers = await api.getMessageVersions(
                  selectedThreadId!,
                  data.message?.id ?? messageId,
                );
                if (resVers.versions && resVers.versions.length > 0) {
                  const key = data.message?.id ?? messageId;
                  versions = { ...versions, [key]: resVers.versions };
                  const activeIdx = resVers.versions.findIndex((v) => v.is_active);
                  currentVersionIndex = {
                    ...currentVersionIndex,
                    [key]: activeIdx >= 0 ? activeIdx : 0,
                  };
                }
              } catch {
                /* ignore */
              }
            }
          } catch {
            /* ignore */
          }
        }
      }

      // Check for notification after regen streaming completes
      if (regenContent) {
        const parsed = parseMessageContent(regenContent);
        if (parsed.notification && !isNotificationDismissed(parsed.notification)) {
          notificationMessage = parsed.notification;
        }
      }
    } catch (e) {
      console.error('Regen failed:', e);
    } finally {
      streaming = false;
      scrollToBottom();
    }
  }

  async function handleSwitchVersion(messageId: number, versionId: number) {
    if (!selectedThreadId) return;
    try {
      const result = await api.switchVersion(selectedThreadId, messageId, versionId);
      if (result.success) {
        // The switched-to message may have a different ID; replace in array
        const oldIdx = messages.findIndex((m) => m.id === messageId);
        const newIdx = messages.findIndex((m) => m.id === result.message.id);
        if (newIdx !== -1) {
          messages[newIdx] = result.message;
        } else if (oldIdx !== -1) {
          messages[oldIdx] = result.message;
        }
        messages = messages; // trigger reactivity
        // Refresh versions
        const vers = await api.getMessageVersions(selectedThreadId, result.message.id ?? messageId);
        const key = result.message.id ?? messageId;
        versions = { ...versions, [key]: vers.versions };
        const activeIdx = vers.versions.findIndex((v) => v.is_active);
        currentVersionIndex = { ...currentVersionIndex, [key]: activeIdx >= 0 ? activeIdx : 0 };
      }
    } catch (e) {
      console.error('Switch version failed:', e);
    }
  }

  /** Fork the conversation up to ``messageId`` into a new thread.
   *
   * User-facing contract: the user clicks the fork icon on a message
   * bubble (or the right-click → "Fork from here" item). The backend
   * returns the new thread's DTO; we splice it into the local
   * ``threads`` array so the sidebar reflects it, then redirect the
   * chat view to the new id via the existing ``selectThread`` path
   * (so all the usual post-thread-switch bookkeeping — pagination
   * reset, scroll-to-bottom, stats refresh, version cache — runs).
   *
   * Failure modes:
   *   * Network / 5xx → catch block surfaces a translated error toast.
   *   * 404 → the source thread or ``messageId`` is gone (e.g. another
   *     tab deleted it). We show a friendlier "no longer in the
   *     active chain" message because the bare ``detail`` ("Thread
   *     7 was not found") is too generic to act on.
   */
  async function handleFork(messageId: number) {
    if (!selectedThreadId || streaming) return;
    try {
      notificationMessage = t('message.fork_started', lang);
      const newThread = await api.forkThread(selectedThreadId, messageId);
      // Prepend to the active-thread list so selectThread() finds
      // the new thread in the array immediately. BotPreviewPage
      // owns the per-bot tree view and refreshes independently
      // when the user navigates back there.
      threads = [newThread, ...threads];
      await selectThread(newThread.id);
    } catch (e) {
      console.error('Fork failed:', e);
      const detail = e instanceof Error ? e.message : String(e);
      // The backend's ``detail`` for 404 is "Message X was not found
      // in thread Y" — replace it with a UX-shaped message instead.
      const isNotFound = /404|Not\s*Found|was not found/i.test(detail);
      notificationMessage = isNotFound
        ? t('message.fork_not_found', lang)
        : t('message.fork_failed', lang, { detail });
    }
  }

  function handleAction(text: string) {
    if (!streaming) {
      sendMessage(text);
    }
  }

  // ── UI helpers ──

  function scrollToBottom(force = false) {
    // Hide the jump button immediately so it doesn't linger after click.
    if (force) showJumpToBottom = false;
    // Two-phase: `tick()` awaits Svelte's DOM flush, then a rAF
    // guarantees the browser has actually laid out the new messages
    // (scrollHeight is computed at layout time, not at DOM-insert time).
    // Without this, scrolling right after `messages = await …` can
    // hit a stale scrollHeight and land in the middle.
    void (async () => {
      await tick();
      await new Promise(requestAnimationFrame);
      if (chatScroll) {
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
      // The second rAF is here because of `content-visibility: auto`
      // on `.mb-row` (see MessageBubble.svelte). The first rAF runs
      // before the browser has finished laying out the off-screen
      // placeholders into real heights — at that point scrollHeight
      // is still based on `contain-intrinsic-size: auto 140px` and
      // our scrollTop lands at the *placeholder* bottom, not the
      // *real* bottom. After the next frame the placeholders are
      // resolved to actual heights, scrollHeight grows, and we have
      // to scroll again to compensate.
      await new Promise(requestAnimationFrame);
      if (force || !showJumpToBottom) {
        if (chatScroll) {
          chatScroll.scrollTop = chatScroll.scrollHeight;
        }
      }
    })();
  }

  // Derive last user message index — when the last message is from the user
  // (no bot response yet), show retry to re-prompt the LLM
  const lastUserMessageIndex = $derived.by(() => {
    if (messages.length === 0 || streaming) return -1;
    const lastIdx = messages.length - 1;
    return messages[lastIdx].role === 'user' ? lastIdx : -1;
  });

  async function handleRetry() {
    if (lastUserMessageIndex < 0) return;
    const lastUserMsg = messages[lastUserMessageIndex];

    // If the message has an ID (saved in DB), use the retry endpoint
    // to avoid creating a duplicate user message
    if (lastUserMsg.id !== null) {
      // Keep the user message visible — just remove anything after it
      messages = messages.slice(0, lastUserMessageIndex + 1);
      streaming = true;

      // Track whether retry hit an error so the finally block doesn't
      // overwrite our error bubble with a server re-fetch.
      let retryFailed = false;

      try {
        const resp = await api.retryMessage(
          selectedThreadId!,
          lastUserMsg.id!,
          selectedBotId!,
          selectedPersonaId,
        );
        if (!resp.ok) {
          let detail = `HTTP ${resp.status}`;
          try {
            const body = await resp.json();
            detail = body.detail || detail;
          } catch {
            /* ignore */
          }
          throw new Error(detail);
        }

        const reader = resp.body?.getReader();
        if (!reader) throw new Error('No reader');

        // Add empty assistant bubble
        messages = [
          ...messages,
          {
            branch_group: null,
            branch_index: 0,
            content: '',
            created_at: null,
            id: null,
            is_active: true,
            reasoning: '',
            role: 'assistant',
            short_content: '',
          },
        ];
        let buffer = '';
        let assistantContent = '';
        let assistantReasoning = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += new TextDecoder().decode(value);
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'chunk') {
                assistantContent += data.content;
                messages[messages.length - 1] = {
                  branch_group: null,
                  branch_index: 0,
                  content: assistantContent,
                  created_at: null,
                  id: null,
                  is_active: true,
                  reasoning: assistantReasoning || undefined,
                  role: 'assistant',
                  short_content: '',
                };
                scrollToBottom();
              } else if (data.type === 'reasoning') {
                assistantReasoning += data.content;
                messages[messages.length - 1] = {
                  ...messages[messages.length - 1],
                  reasoning: assistantReasoning,
                };
              } else if (data.type === 'error') {
                // Server-side error mid-stream — mark as failed so finally
                // doesn't re-fetch and wipe our error bubble.
                retryFailed = true;
                messages = messages.slice(0, -1);
                messages = [
                  ...messages,
                  {
                    branch_group: null,
                    branch_index: 0,
                    content: `⚠️ ${data.detail || 'Failed to generate response'}`,
                    created_at: null,
                    id: null,
                    is_active: true,
                    role: 'assistant',
                    short_content: '',
                  },
                ];
                scrollToBottom();
              }
            } catch {
              /* ignore */
            }
          }
        }
      } catch (e) {
        console.error('Retry failed:', e);
        retryFailed = true;
        messages = [
          ...messages,
          {
            branch_group: null,
            branch_index: 0,
            content: `⚠️ Error: ${e}`,
            created_at: null,
            id: null,
            is_active: true,
            role: 'assistant',
            short_content: '',
          },
        ];
      } finally {
        streaming = false;
        scrollToBottom();
        // Re-fetch only on success — on failure we already showed the error
        // bubble above and a server refresh would clobber it (the "blink and
        // disappear" bug: ⚠️ appears, then listMessages wipes it).
        if (!retryFailed && selectedThreadId) {
          const tid = selectedThreadId;
          api
            .listMessages(tid)
            .then((msgs) => {
              messages = msgs;
              void refreshThreadStats(tid);
              scrollToBottom();
            })
            .catch(() => {});
        }
      }
      return;
    }

    // No ID — message wasn't saved to DB, send as new
    messages = messages.slice(0, lastUserMessageIndex);
    await sendMessage(lastUserMsg.content);
  }

  const selectedPersona = $derived(personas.find((p) => p.id === selectedPersonaId) || null);

  // ── Context compression ──

  async function checkSummary(threadId: number) {
    try {
      const thread = await api.getThread(threadId);
      hasSummary = !!thread.summary;
    } catch {
      hasSummary = false;
    }
  }

  async function compressContext() {
    if (compressing || !selectedThreadId) return;
    compressing = true;
    try {
      await api.summarizeThread(selectedThreadId);
      hasSummary = true;
    } catch (e) {
      console.error('Summarization failed:', e);
    } finally {
      compressing = false;
    }
  }

  async function exportThread() {
    try {
      await api.exportChat(selectedThreadId!);
    } catch (e) {
      console.error('Export failed:', e);
      notificationMessage = t('chat.export_failed', lang);
    }
  }

  // ── Edit modal ──

  function openEditModal(msg: Message) {
    editMessageId = msg.id;
    editContent = msg.content;
    // ``Message.state`` is the new world-state snapshot column
    // (assistant only). We only show the state textarea for
    // assistant turns; for user messages the value stays null
    // and the modal hides the second textarea via ``{#if}``.
    editMessageState = msg.role === 'assistant' ? (msg.state ?? null) : null;
    showEditModal = true;
  }

  function closeEditModal() {
    showEditModal = false;
    editMessageId = null;
    editContent = '';
    editMessageState = null;
  }

  /**
   * Save the edit modal's content + state via the EditMessageModal.
   *
   * Three-way contract for ``newState`` (the second positional arg):
   *   - ``null`` + the message had no state column → don't send the
   *     ``state`` key at all (server-side copies original state).
   *   - non-null string → send verbatim; empty string clears the
   *     snapshot explicitly.
   *   - ``null`` + the message had a state → send no key, server
   *     preserves the original on the new branch (branching fidelity).
   *
   * In short: the modal only forwards a state string when we trust
   * the typed value (i.e. always for assistant messages with a
   * state column). For user-message edits the parent passes ``null``
   * and the modal's ``{#if messageState !== null}`` branch is hidden
   * anyway.
   */
  async function saveEditModal(text: string, newState: null | string) {
    if (selectedThreadId === null || editMessageId === null) return;
    if (!text.trim()) return;
    try {
      await api.updateMessage(selectedThreadId, editMessageId, text, newState);
      closeEditModal();
      messages = await api.listMessages(selectedThreadId);
      void refreshThreadStats(selectedThreadId);
      // Sync versions state — without this the ◀ N/M ▶ counter stays
      // on "1/1" until something else (regen / switch version) re-syncs.
      const synced = syncVersionsStateFromMessages(messages);
      versions = { ...versions, ...synced.versions };
      currentVersionIndex = { ...currentVersionIndex, ...synced.currentVersionIndex };
    } catch (e) {
      console.error('Failed to update message:', e);
    }
  }

  // ── Delete ──

  function confirmDelete(msgId: null | number) {
    if (msgId === null) return;
    deletingMsgId = msgId;
    showDeleteConfirm = true;
  }

  async function executeDelete() {
    if (selectedThreadId === null || deletingMsgId === null) return;
    try {
      await api.cascadeDeleteMessages(selectedThreadId, deletingMsgId);
      showDeleteConfirm = false;
      deletingMsgId = null;
      messages = await api.listMessages(selectedThreadId);
      void refreshThreadStats(selectedThreadId);
      // Sync versions state — the deleted message may have had a
      // branch group; refetched messages reflect the new state.
      const synced = syncVersionsStateFromMessages(messages);
      versions = { ...versions, ...synced.versions };
      currentVersionIndex = { ...currentVersionIndex, ...synced.currentVersionIndex };
    } catch (e) {
      console.error('Failed to delete messages:', e);
    }
  }

  function cancelDelete() {
    showDeleteConfirm = false;
    deletingMsgId = null;
  }

  function closeNotification() {
    if (notificationMessage) {
      dismissNotification(notificationMessage);
      notificationMessage = null;
    }
  }
</script>

<div class="chat-page" class:chat-with-bot={!!bot}>
  {#if loading}
    <div class="chat-loading">
      <Loading type="dots" size="lg" />
    </div>
  {:else if !bot}
    <div class="chat-recent-view">
      <div class="chat-recent-header">
        <h2 class="chat-recent-title">{t('chat.recent.title', lang)}</h2>
        <p class="chat-recent-subtitle">{t('chat.recent.subtitle', lang)}</p>
      </div>
      <div class="chat-recent-list">
        <RecentChats
          threads={crossBotThreads}
          {loading}
          onselectThread={(botId, threadId) =>
            (window.location.hash = `/chat?bot=${botId}&thread=${threadId}`)}
          ondeleteThread={async (threadId) => {
            await api.deleteThread(threadId);
            crossBotThreads = crossBotThreads.filter((t) => t.thread_id !== threadId);
          }}
        />
      </div>
    </div>
  {:else}
    <div class="chat-main">
      <ChatHeader
        botName={bot.name}
        botAvatarPath={bot.avatar_path}
        messageCount={realMessageCount}
        totalTokens={realTokenEstimate}
        {hasSummary}
        {compressing}
        {lang}
        onbotClick={() => (window.location.hash = `/bot/${bot!.id}`)}
        oneditbot={() => (window.location.hash = `/bots/${bot!.id}`)}
        ontoggleThreads={() => (showThreadDrawer = !showThreadDrawer)}
        oncompress={compressContext}
        ondeleteThread={deleteCurrentThread}
        onexport={exportThread}
        onnewthread={newThread}
      />

      <div class="chat-messages" bind:this={chatScroll} onscroll={handleChatScroll}>
        {#if hasMoreOlder}
          <!--
            Sentinel element for the IntersectionObserver wired up in
            `$effect` above. Visually invisible — we just need a
            zero-height marker at the top of the list that becomes
            "near the viewport" as the user scrolls upward. A tiny
            spinner is overlaid only while a fetch is in flight.
          -->
          <div bind:this={loadMoreSentinel} class="load-more-sentinel" aria-hidden="true"></div>
          {#if loadingMore}
            <div class="flex justify-center my-2 text-theme-secondary text-xs">
              <span class="inline-flex items-center gap-2">
                <span class="lm-spinner"></span>
                {lang === 'ru' ? 'Загрузка более ранних сообщений…' : 'Loading older messages…'}
              </span>
            </div>
          {/if}
        {/if}
        {#if !greetingLocked && availableGreetings.length > 1}
          <div class="flex items-center justify-center gap-3 my-3 text-theme-secondary text-sm">
            <button
              class="px-2 py-1 rounded hover:bg-theme-surface/80 transition"
              onclick={() =>
                (selectedGreetingIndex =
                  (selectedGreetingIndex - 1 + availableGreetings.length) %
                  availableGreetings.length)}
              aria-label="Previous greeting"
            >
              ◀
            </button>
            <span>
              {selectedGreetingIndex + 1} / {availableGreetings.length}
            </span>
            <button
              class="px-2 py-1 rounded hover:bg-theme-surface/80 transition"
              onclick={() =>
                (selectedGreetingIndex = (selectedGreetingIndex + 1) % availableGreetings.length)}
              aria-label="Next greeting"
            >
              ▶
            </button>
          </div>
        {/if}
        {#each displayedMessagesView as msg, i (`${msg.id ?? 'n'}-${i}`)}
          {@const hasDebug = DEV_MODE && msg.id != null && debugByMessage[msg.id] != null}
          <!--
            The wrapper carries `data-msg-id` so `loadMoreOlder`'s
            scroll-anchor algorithm can locate a specific message in
            the DOM without having to dig into MessageBubble's
            internal layout. Width 100% is required because the
            flex-column child of `.chat-messages` would otherwise
            shrink to fit the MessageBubble's intrinsic content
            width, breaking the per-message vertical layout.
          -->
          <div class="msg-anchor" data-msg-id={msg.id ?? null}>
            <MessageBubble
              {msg}
              {streaming}
              isLast={i === messages.length - 1}
              showRetry={lastUserMessageIndex >= 0 &&
                msg.role === 'user' &&
                i === lastUserMessageIndex}
              botName={bot.name}
              botAvatarPath={bot.avatar_path}
              personaAvatarPath={selectedPersona?.avatar_path ?? null}
              personaName={selectedPersona?.name ?? 'U'}
              versions={versions[msg.id ?? -1] ?? []}
              files={messageFiles[msg.id ?? -1] ?? []}
              {lang}
              onedit={openEditModal}
              ondelete={confirmDelete}
              onfork={(m) => handleFork(m.id!)}
              onregenerate={() => handleRegenerate(msg.id!)}
              onretry={handleRetry}
              onaction={handleAction}
              onswitchversion={(vid: number) => handleSwitchVersion(msg.id!, vid)}
              onopendebug={hasDebug ? () => openDebugModal(msg.id!) : undefined}
            />
          </div>
        {/each}
        <div bind:this={messagesEnd}></div>
        {#if showJumpToBottom}
          <button
            class="chat-jump-btn"
            type="button"
            aria-label="Scroll to latest message"
            title="Scroll to latest message"
            onclick={() => scrollToBottom(true)}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <polyline points="19 12 12 19 5 12"></polyline>
            </svg>
          </button>
        {/if}
      </div>

      <ChatInput
        {streaming}
        {lang}
        botType={bot?.bot_type || 'rp'}
        threadId={selectedThreadId || 0}
        botId={selectedBotId}
        onsend={sendMessage}
        onstop={stopStreaming}
      />
    </div>

    {#if showThreadDrawer}
      <ThreadDrawer
        {threads}
        {selectedThreadId}
        botName={bot.name}
        {lang}
        onselect={selectThread}
        onnew={newThread}
        onclose={() => (showThreadDrawer = false)}
        ondelete={(id) => {
          threads = threads.filter((t) => t.id !== id);
          if (selectedThreadId === id) {
            if (threads.length > 0) selectThread(threads[0].id);
            else {
              selectedThreadId = null;
              messages = [];
            }
          }
        }}
        onrename={(id, name) => {
          const idx = threads.findIndex((t) => t.id === id);
          if (idx !== -1) threads[idx] = { ...threads[idx], name };
          threads = threads;
        }}
      />
    {/if}
  {/if}

  <EditMessageModal
    show={showEditModal}
    content={editContent}
    messageState={editMessageState}
    onsave={saveEditModal}
    onclose={closeEditModal}
  />

  <DeleteConfirmModal show={showDeleteConfirm} onconfirm={executeDelete} oncancel={cancelDelete} />

  {#if openDebugId !== null && debugByMessage[openDebugId]}
    {@const debugMsg = messages.find((m) => m.id === openDebugId)}
    <LLMDebugModal
      debug={debugByMessage[openDebugId]}
      usage={usageByMessage[openDebugId] ?? null}
      state={debugMsg?.state ?? null}
      onclose={closeDebugModal}
    />
  {/if}
</div>

<NotificationModal
  show={notificationMessage !== null}
  message={notificationMessage ?? ''}
  onclose={closeNotification}
/>

<PersonaSelectModal
  show={showPersonaModal}
  {personas}
  botId={selectedBotId}
  {lang}
  onselect={onNewThreadWithPersona}
  onclose={() => (showPersonaModal = false)}
/>

<style>
  :root {
    --chat-bg: #f5f5f7;
    --chat-bg-card: #ffffff;
    --chat-border: rgba(0, 0, 0, 0.06);
    --chat-text: #1d1d1f;
    --chat-text-secondary: #6e6e73;
    --chat-text-tertiary: #86868b;
  }
  :root.dark {
    --chat-bg: #07080a;
    --chat-bg-card: #101111;
    --chat-border: rgba(255, 255, 255, 0.06);
    --chat-text: #f9f9f9;
    --chat-text-secondary: #9c9c9d;
    --chat-text-tertiary: #6a6b6c;
  }

  .chat-page {
    display: flex;
    height: 100vh;
    background: var(--chat-bg);
    color: var(--chat-text);
  }

  /* ─── Loading ─── */
  .chat-loading {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* ─── Recent chats (no bot selected) ─── */
  .chat-recent-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .chat-recent-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--chat-border);
    flex-shrink: 0;
  }
  .chat-recent-title {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 18px;
    font-weight: 500;
    letter-spacing: 0.2px;
    color: var(--chat-text);
    margin: 0;
  }
  .chat-recent-subtitle {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: 0.2px;
    color: var(--chat-text-secondary);
    margin: 4px 0 0;
  }
  .chat-recent-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
  }

  /* ─── Chat main (bot selected) ─── */
  .chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    position: relative;
  }
  /*
   * The `<div data-msg-id>` wrapper around each MessageBubble exists
   * purely to give the scroll-anchor algorithm a stable selector.
   * `display: contents` makes the wrapper a "ghost" element: it
   * stays in the DOM (so querySelector can find it) but does not
   * generate a layout box. The MessageBubble's own .mb-row becomes
   * the direct flex child of .chat-messages, preserving the
   * pre-wrapper layout exactly. We previously used a regular
   * `<div>` here and it added an extra block-level box per
   * message, breaking the per-message flex spacing.
   */
  .msg-anchor {
    display: contents;
  }
  /*
   * The jump-to-bottom button is rendered *inside* `.chat-messages` so
   * it lives in the chat subtree (no need to coordinate with the page
   * layout), but its `position` is `sticky` (not `absolute`).
   *
   * Why not `absolute`? In a flex column with `overflow-y: auto`, an
   * absolutely-positioned descendant is laid out against the *content
   * box* of the scroll container, so it scrolls with the messages —
   * i.e. if the user scrolls up to read history, the button flies off
   * the top of the visible area. (This was the bug.)
   *
   * Why does `sticky` work? `position: sticky` with `bottom: 16px`
   * pins the element to the visible bottom edge of its scrolling
   * ancestor — exactly what we want. The `align-self: flex-end` keeps
   * it right-aligned in the column. The `margin-top: -54px` overlaps
   * the chat padding so the button doesn't push messages down when
   * it appears.
   */
  .chat-jump-btn {
    position: fixed;
    align-self: flex-end;
    bottom: 100px;
    margin-top: -54px; /* overlap the bottom padding so it doesn't push messages */
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--ch-border, rgba(0, 0, 0, 0.08));
    border-radius: 999px;
    background: var(--ch-bg, #ffffff);
    color: var(--ch-text-secondary, #6e6e73);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
    cursor: pointer;
    transition:
      transform 0.15s ease,
      opacity 0.15s ease,
      color 0.15s ease,
      background 0.15s ease;
    animation: chat-jump-in 0.18s ease-out;
  }
  .chat-jump-btn:hover {
    transform: translateY(-1px);
    color: var(--ch-text, #1d1d1f);
    background: color-mix(in srgb, var(--ch-bg, #ffffff) 92%, var(--ch-hover, rgba(0, 0, 0, 0.04)));
  }
  :root.dark .chat-jump-btn {
    border-color: rgba(255, 255, 255, 0.1);
    background: #1a1b1c;
    color: #c7c7c8;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
  }
  :root.dark .chat-jump-btn:hover {
    background: #222425;
    color: #f9f9f9;
  }
  @keyframes chat-jump-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* ─── Lazy-load sentinel ─────────────────────────────────────────
   * The IntersectionObserver watches this element from inside
   * `chatScroll`. We keep it visually zero-height so the layout
   * doesn't shift, but `pointer-events: none` is belt-and-braces in
   * case a parent ever gives it padding.
   */
  .load-more-sentinel {
    height: 1px;
    width: 100%;
    pointer-events: none;
    /* content-visibility: auto is set on .mb-row (MessageBubble)
     * for the off-screen DOM skip. The sentinel itself is a single
     * 1px line so leaving it as-is is fine — there's nothing to
     * render. */
  }

  @keyframes lm-spin {
    to {
      transform: rotate(360deg);
    }
  }
  .lm-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: lm-spin 0.7s linear infinite;
    opacity: 0.6;
  }
</style>
