<!-- NotificationModal — pre-styled modal with a centered icon, message,
     and OK button. Six semantic variants: success / info / warning /
     error / celebration / help. The icon is a small colored SVG drawn
     over a soft pastel circle background — all icons live in a lookup
     table below and are picked by the `variant` prop (default 'info').

     The icons are outline-style at 24x24 viewBox, stroke 1.8, with a
     subtle fill (color at ~15% opacity) to give a "tinted" feel. The
     circle background behind the icon is a tinted gradient that matches
     the icon's hue at very low saturation (pastel). This makes every
     variant feel distinct without being loud. -->

<script lang="ts">
  import Modal from './Modal.svelte';

  // Six icon variants. Each icon is a 24x24 viewBox SVG, drawn with
  // currentColor strokes and a 15%-opacity fill in the same hue. The
  // circle background lives in the .nm-icon-bg div via CSS classes
  // (nm-bg-{variant}); the icon's stroke color is set via the same
  // class on the SVG. This keeps the markup tiny while still giving
  // every variant its own visual identity.
  type Variant = 'celebration' | 'error' | 'help' | 'info' | 'success' | 'warning';

  // SVG path data only — the wrapper <g> with stroke + fill is added
  // by the template so we don't repeat the styling 6 times.
  const ICONS: Record<Variant, string> = {
    // 4: celebration — party popper (cone + confetti)
    celebration: `<path d="M 5 19 L 12 5 L 16 9 L 9 19 Z" fill="currentColor" fill-opacity="0.15" />
                  <line x1="14" y1="4" x2="15" y2="5" stroke-linecap="round" />
                  <line x1="18" y1="6" x2="19" y2="7" stroke-linecap="round" />
                  <line x1="17" y1="3" x2="17" y2="4" stroke-linecap="round" />
                  <line x1="20" y1="10" x2="21" y2="11" stroke-linecap="round" />`,
    // 3: error — circle + X
    error: `<circle cx="12" cy="12" r="9" fill="currentColor" fill-opacity="0.15" />
            <line x1="9" y1="9" x2="15" y2="15" stroke-linecap="round" />
            <line x1="15" y1="9" x2="9" y2="15" stroke-linecap="round" />`,
    // 5: help — circle + question mark
    help: `<circle cx="12" cy="12" r="9" fill="currentColor" fill-opacity="0.15" />
           <path d="M 9 9 Q 9 6 12 6 Q 15 6 15 9 Q 15 11 12 12 L 12 14" stroke-linecap="round" stroke-linejoin="round" />
           <circle cx="12" cy="16.5" r="0.9" fill="currentColor" stroke="none" />`,
    // 1: info — circle + "i" (lowercase i shape: dot on top, vertical bar)
    info: `<circle cx="12" cy="12" r="9" fill="currentColor" fill-opacity="0.15" />
           <line x1="12" y1="11" x2="12" y2="16" stroke-linecap="round" />
           <circle cx="12" cy="8" r="0.9" fill="currentColor" stroke="none" />`,
    // 0: success — circle + checkmark
    success: `<circle cx="12" cy="12" r="9" fill="currentColor" fill-opacity="0.15" />
              <path d="M 8 12 L 11 15 L 16 9" />`,
    // 2: warning — triangle + exclamation
    warning: `<path d="M 12 4 L 21 19 L 3 19 Z" fill="currentColor" fill-opacity="0.15" />
              <line x1="12" y1="10" x2="12" y2="14" stroke-linecap="round" />
              <circle cx="12" cy="16.5" r="0.9" fill="currentColor" stroke="none" />`,
  };

  const {
    message = '',
    onclose,
    show = false,
    variant = 'info' as Variant,
  }: {
    message?: string;
    onclose?: () => void;
    show?: boolean;
    /** Visual style — picks the icon and background color. Default 'info'. */
    variant?: Variant;
  } = $props();

  const iconPath = $derived(ICONS[variant]);

  function close() {
    onclose?.();
  }
</script>

<Modal open={show} size="sm" {onclose}>
  <div class="nm-body">
    <div class="nm-icon-wrap nm-bg-{variant}" data-variant={variant}>
      <svg
        class="nm-icon"
        viewBox="0 0 24 24"
        width="40"
        height="40"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        {@html iconPath}
      </svg>
    </div>
    <p class="nm-message">{message}</p>
    <button class="nm-btn" onclick={close}>OK</button>
  </div>
</Modal>

<style>
  .nm-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 8px 0;
  }
  .nm-icon-wrap {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 14px;
    /* Each variant sets a pastel gradient background and a color for
       the SVG stroke. The color is what makes the icon "ring" in the
       right semantic hue. */
  }
  /* Pastel background colors per variant. Saturation 60..70%,
     lightness 90..94% — soft tinted circles, never loud. */
  .nm-bg-success {
    background: linear-gradient(135deg, hsl(150 65% 92%), hsl(160 70% 88%));
    color: hsl(155 55% 32%);
  }
  .nm-bg-info {
    background: linear-gradient(135deg, hsl(210 70% 92%), hsl(220 65% 88%));
    color: hsl(215 60% 38%);
  }
  .nm-bg-warning {
    background: linear-gradient(135deg, hsl(40 75% 92%), hsl(35 70% 88%));
    color: hsl(35 70% 36%);
  }
  .nm-bg-error {
    background: linear-gradient(135deg, hsl(0 70% 93%), hsl(355 65% 89%));
    color: hsl(355 60% 38%);
  }
  .nm-bg-celebration {
    background: linear-gradient(135deg, hsl(280 65% 92%), hsl(310 60% 88%));
    color: hsl(290 55% 36%);
  }
  .nm-bg-help {
    background: linear-gradient(135deg, hsl(195 65% 92%), hsl(180 60% 88%));
    color: hsl(195 60% 34%);
  }
  .nm-message {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    color: var(--ray-text, #f9f9f9);
    margin: 0 0 20px 0;
    max-width: 360px;
  }
  .nm-btn {
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 32px;
    border-radius: 8px;
    border: none;
    background: var(--ray-accent, #8b5cf6);
    color: #fff;
    cursor: pointer;
    transition: background 0.12s ease;
  }
  .nm-btn:hover {
    background: color-mix(in srgb, var(--ray-accent, #8b5cf6) 80%, #000);
  }
</style>
