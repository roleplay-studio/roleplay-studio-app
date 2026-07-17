<!-- TTSButton — play/stop button for a single message's text-to-speech.

States:
    * ``idle``     — speaker glyph; clicking triggers synthesis.
    * ``loading``  — spinner; the FIRST click per message calls
                    ``/api/tts/synthesize`` (cached afterwards).
    * ``playing``  — square glyph; clicking stops the local <audio>.
    * ``error``    — speaker glyph with the Tooltip in error variant.

Disabling semantics:
    * On the first ``TTSDisabledError`` we set a sessionStorage flag
      so the route can hide *every* TTSButton in the page (TTS is a
      server-side switch — once we see 503 there's no point retrying).
    * Network / provider errors are surfaced inline via the Tooltip
      and let the user retry; we don't disable globally.

Component scope:
    Stateless except for ``<audio>`` + the disabled-flag. Each
    bubble owns its own audio element so playing one message doesn't
    stomp playback of another (a global "current speaker" handler
    would add complexity for a feature that's intentionally opt-in).
-->
<script lang="ts">
  import { onDestroy } from 'svelte';

  import { ttsApi, TTSDisabledError } from '../api';
  import { currentLang, t } from '../i18n';
  import { Tooltip } from './index';

  const {
    content,
  }: {
    /** Plain text to speak — strip markdown before passing in. */
    content: string;
  } = $props();

  // Svelte 5's $state() doesn't take a generic; declare the type
  // separately. The variable is ``playback`` (not ``state``) so the
  // LSP doesn't confuse it with the ``state`` re-exported from
  // various stores elsewhere in the app.
  type Playback = 'error' | 'idle' | 'loading' | 'playing';
  let playback: Playback = $state('idle');
  let errorMessage = $state('');
  // ``cacheId`` is the id the server returned on first successful
  // synthesis — re-used on every subsequent click to skip the
  // /synthesize round-trip and go straight to <audio src=...>.
  let cacheId: null | string = $state(null);
  let lang = $state('en');

  // Disabled flag is global per-tab: once the backend tells us TTS
  // is off (HTTP 503), every TTSButton hides itself. We don't poll
  // again because the operator toggling TTS_PROVIDER requires a
  // backend restart anyway.
  const DISABLED_KEY = 'ttsDisabled';
  let disabled = $state(false);

  if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem(DISABLED_KEY)) {
    disabled = true;
  }

  let audio: HTMLAudioElement | null = null;

  $effect(() => {
    const unsub = currentLang.subscribe((v) => (lang = v));
    return unsub;
  });

  function stopAudio() {
    if (audio) {
      audio.pause();
      // Reset playback position so a fresh start from ``idle``
      // begins at 0. Without this, a paused-then-resumed session
      // restarts mid-track.
      audio.currentTime = 0;
    }
    playback = 'idle';
  }

  async function startPlayback(src: string, id: string) {
    if (audio) {
      audio.pause();
    }
    audio = new Audio(src);
    cacheId = id;
    audio.onended = () => {
      playback = 'idle';
    };
    audio.onerror = () => {
      // ``media_err`` is intentionally generic — browsers expose a
      // code on ``audio.error`` but the code's meaning varies (1..4),
      // and a single friendly fallback is enough for the toast.
      playback = 'error';
      errorMessage = t('message.tts_error', lang);
    };
    try {
      await audio.play();
      playback = 'playing';
    } catch (err) {
      // Autoplay blocking or invalid src — fall back to error UI.
      playback = 'error';
      errorMessage = t('message.tts_error', lang);
      console.error('TTS playback failed', err);
    }
  }

  async function handleClick() {
    if (disabled) return;
    if (playback === 'playing') {
      stopAudio();
      return;
    }
    if (playback === 'loading') return;
    // We have a cache id — try playing straight from disk.
    if (cacheId) {
      await startPlayback(ttsApi.audioUrl(cacheId), cacheId);
      return;
    }
    // Cold start: call /synthesize first.
    playback = 'loading';
    try {
      const resp = await ttsApi.synthesize({ text: content });
      await startPlayback(ttsApi.audioUrl(resp.cache_id), resp.cache_id);
    } catch (err) {
      if (err instanceof TTSDisabledError) {
        disabled = true;
        if (typeof sessionStorage !== 'undefined') {
          try {
            sessionStorage.setItem(DISABLED_KEY, '1');
          } catch {
            // sessionStorage may be unavailable (SSR, private mode);
            // the in-memory flag still hides the button.
          }
        }
        return;
      }
      playback = 'error';
      errorMessage = err instanceof Error ? err.message : t('message.tts_error', lang);
    }
  }

  onDestroy(() => {
    if (audio) {
      audio.pause();
      audio = null;
    }
  });
</script>

{#if !disabled}
  <Tooltip
    text={playback === 'playing'
      ? t('message.tts_stop', lang)
      : playback === 'loading'
        ? t('message.tts_loading', lang)
        : playback === 'error'
          ? errorMessage
          : t('message.tts_play', lang)}
    position="bottom"
    variant={playback === 'error' ? 'error' : 'default'}
  >
    <button
      type="button"
      class="mb-action-btn tts-btn"
      class:is-loading={playback === 'loading'}
      class:is-playing={playback === 'playing'}
      class:is-error={playback === 'error'}
      aria-label={t('message.tts_play', lang)}
      disabled={playback === 'loading'}
      onclick={handleClick}
    >
      {#if playback === 'playing'}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <rect x="6" y="5" width="4" height="14" rx="1"></rect>
          <rect x="14" y="5" width="4" height="14" rx="1"></rect>
        </svg>
      {:else if playback === 'loading'}
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-volume2-icon lucide-volume-2"><path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/></svg>
      {:else}
        <!-- Speaker glyph for idle / error -->
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
        >
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
          <path d="M15.54 8.46a5 5 0 010 7.07"></path>
          <path d="M19.07 4.93a10 10 0 010 14.14"></path>
        </svg>
      {/if}
    </button>
  </Tooltip>
{/if}

<style>
  /* matches the surrounding mb-action-btn footprint so the row stays
     neatly aligned with regenerate / edit / delete buttons. */
  .tts-btn {
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--mb-text-tertiary);
    transition: color 0.15s ease;
  }

  .tts-btn:hover:not(:disabled) {
    color: #818cf8;
    /* Tailwind: text-indigo-400 — pulled inline so the file stays
       self-contained without @apply. */
  }

  .tts-btn.is-playing {
    color: #818cf8;
  }

  .tts-btn.is-error {
    color: var(--mb-red, #ff3b30);
  }

  .tts-btn.is-error:hover {
    color: var(--mb-red, #ff6363);
  }

  .tts-btn:disabled {
    cursor: default;
  }

  @keyframes tts-spin {
    to {
      transform: rotate(360deg);
    }
  }

  .tts-spinner {
    animation: tts-spin 0.9s linear infinite;
  }
</style>
