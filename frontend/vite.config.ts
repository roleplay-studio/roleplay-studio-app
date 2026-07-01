import { svelte } from '@sveltejs/vite-plugin-svelte';
/// <reference types="vitest" />
import { defineConfig } from 'vite';

export default defineConfig({
  clearScreen: false,
  plugins: [svelte()],
  resolve: {
    conditions: ['development', 'browser'],
  },
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      ignored: ['**/src-tauri/**'],
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{ts,js}'],
    setupFiles: './vitest.setup.ts',
  },
});
