<!-- TTSButtonDemo — preview the message TTS button in three content shapes.

Uses the real ``TTSButton`` component so the snapshot test catches
any drift in the icon set / disabled handling. Plays are no-ops in
jsdom (no ``Audio``), but state transitions (idle → loading → error)
require a real browser; the demo just shows the visual footprint
plus a "disabled" variant for documentation.
-->
<script lang="ts">
  import TTSButton from '../../TTSButton.svelte';
</script>

<div class="tts-stack">
  <div class="tts-row">
    <span class="tts-label">Idle</span>
    <TTSButton content="Hello, traveller. Welcome to the moonlit garden." />
  </div>
  <div class="tts-row">
    <span class="tts-label">Short</span>
    <TTSButton content="OK." />
  </div>
  <div class="tts-row">
    <span class="tts-label">Long</span>
    <TTSButton
      content="The ancient gate creaked open, revealing a courtyard overgrown with silver moss. Beyond it, the silhouette of a tower."
    />
  </div>
  <p class="tts-hint">
    Hover to see the "Listen" tooltip. The button calls
    <code>POST /api/tts/synthesize</code> on first click; subsequent clicks play the cached MP3 from
    <code>GET /api/tts/audio/&lt;id&gt;</code>. When <code>TTS_PROVIDER=disabled</code> on the server
    the button hides itself for the rest of the session.
  </p>
</div>

<style>
  .tts-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .tts-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .tts-label {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    width: 70px;
  }
  .tts-hint {
    font-family: 'Maple Mono', monospace;
    font-size: 11px;
    color: var(--ray-text-tertiary);
    margin: 6px 0 0;
    line-height: 1.55;
    max-width: 480px;
  }
  .tts-hint code {
    background: var(--ray-bg-elevated, rgba(255, 255, 255, 0.06));
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 10.5px;
  }
</style>
