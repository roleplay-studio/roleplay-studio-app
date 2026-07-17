import './app.css';
import 'flyonui/flyonui.js';
import { mount } from 'svelte';

import App from './App.svelte';

const app = mount(App, {
  target: document.getElementById('app')!,
});

export default app;

/**
 * Phase 5.3 — Register the service worker.
 *
 * We only register in production builds (no SW in `vite dev` — HMR breaks).
 * Production is signaled by `import.meta.env.PROD`. We also skip the
 * SW during E2E tests via the `?no-sw` query string so test runners
 * don't register persistent workers between specs.
 *
 * Errors are silently swallowed — a failed SW registration shouldn't
 * break the app. The user just won't get offline support.
 */
if (import.meta.env.PROD && !window.location.search.includes('no-sw')) {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((err) => {
        console.warn('[PWA] Service worker registration failed:', err);
      });
    });
  }
}
