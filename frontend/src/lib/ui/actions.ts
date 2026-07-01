// UI Actions — reusable Svelte actions

/**
 * Auto-grow textarea to fit content.
 * Supports both programmatic height changes (input) and user-driven resize handle.
 */
export function autogrow(node: HTMLTextAreaElement) {
  function resize() {
    node.style.height = 'auto';
    node.style.height = node.scrollHeight + 'px';
  }
  resize();
  node.addEventListener('input', resize);
  node.addEventListener('resize', resize);
  return {
    destroy() {
      node.removeEventListener('input', resize);
      node.removeEventListener('resize', resize);
    },
  };
}

/**
 * Focus trap for modals — keeps focus inside the element.
 */
export function trapFocus(node: HTMLElement) {
  const focusable = node.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  node.addEventListener('keydown', handleKeydown);
  first?.focus();

  return {
    destroy() {
      node.removeEventListener('keydown', handleKeydown);
    },
  };
}
