import { writable } from 'svelte/store';

/** Whether the sidebar is currently visible. */
export const sidebarOpen = writable(true);

/** Whether we're below the mobile breakpoint (768px). */
export const isMobile = writable(false);
