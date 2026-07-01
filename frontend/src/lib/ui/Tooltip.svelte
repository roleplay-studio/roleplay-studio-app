<!-- Tooltip — CSS-only tooltip with Raycast-style design -->
<!-- Usage: <Tooltip text="Tooltip content" position="top"><button>Hover me</button></Tooltip> -->
<!-- Positions: top | bottom | left | right -->
<!-- Variants: default | info | error -->
<script lang="ts">
  const {
    children,
    class: className = '',
    position = 'top',
    text = '',
    variant = 'default',
  }: {
    children?: import('svelte').Snippet;
    class?: string;
    position?: 'bottom' | 'left' | 'right' | 'top';
    text: string;
    variant?: 'default' | 'error' | 'info';
  } = $props();
</script>

<div class="rt-tooltip rt-{position} rt-{variant} {className}">
  {#if children}
    {@render children()}
  {/if}
  <div class="rt-tip">{text}</div>
</div>

<style>
  .rt-tooltip {
    position: relative;
    display: inline-flex;
  }
  .rt-tip {
    position: absolute;
    z-index: 60;
    padding: 5px 10px;
    border-radius: 6px;
    font-family: 'Maple Mono', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.2px;
    white-space: nowrap;
    pointer-events: none;
    opacity: 0;
    transform: translateY(4px);
    transition: all 0.15s ease;
    background: var(--ray-tooltip-bg, rgba(30, 30, 32, 0.95));
    color: var(--ray-tooltip-text, #f9f9f9);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
  }
  .rt-tooltip:hover .rt-tip {
    opacity: 1;
    transform: translateY(0);
  }

  /* ── Positions ── */
  .rt-top .rt-tip {
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%) translateY(4px);
  }
  .rt-top:hover .rt-tip {
    transform: translateX(-50%) translateY(0);
  }

  .rt-bottom .rt-tip {
    top: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%) translateY(-4px);
  }
  .rt-bottom:hover .rt-tip {
    transform: translateX(-50%) translateY(0);
  }

  .rt-left .rt-tip {
    right: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%) translateX(4px);
  }
  .rt-left:hover .rt-tip {
    transform: translateY(-50%) translateX(0);
  }

  .rt-right .rt-tip {
    left: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%) translateX(-4px);
  }
  .rt-right:hover .rt-tip {
    transform: translateY(-50%) translateX(0);
  }

  /* ── Variants ── */
  .rt-info .rt-tip {
    background: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 85%, transparent);
    color: #fff;
    border-color: color-mix(in srgb, var(--ray-blue, hsl(202, 100%, 67%)) 20%, transparent);
  }
  .rt-error .rt-tip {
    background: color-mix(in srgb, var(--ray-red, #ff6363) 85%, transparent);
    color: #fff;
    border-color: color-mix(in srgb, var(--ray-red, #ff6363) 20%, transparent);
  }
</style>
