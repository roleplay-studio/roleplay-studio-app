import { svelte } from '@sveltejs/vite-plugin-svelte';
/// <reference types="vitest" />
import { defineConfig, loadEnv, type UserConfig } from 'vite';

// Default API target for `vite dev` when running on the host
// without Docker. Matches the value in src/lib/api.ts so the
// proxy and the direct-fetch path agree by default.
const HOST_API = 'http://127.0.0.1:55245';

// Type-aliased wrapper around defineConfig that preserves the
// Vitest `test` field. Without the cast the TS compiler refuses
// the `test` property once we wrap the config in a function
// (the function-return overload is typed as UserConfig, not the
// merged UserConfig & { test } from vitest/config).
export default defineConfig((env_): UserConfig & { test?: unknown } => {
  // loadEnv reads .env / .env.local in the frontend/ directory.
  // We do this so a developer can drop VITE_API_PROXY into a
  // frontend/.env.local without touching the repo.
  const env = loadEnv(env_.mode, process.cwd(), '');
  const apiProxy = env.VITE_API_PROXY || HOST_API;

  return {
    clearScreen: false,
    plugins: [svelte()],
    resolve: {
      conditions: ['development', 'browser'],
    },
    server: {
      // Bind on all interfaces inside Docker; harmless on the
      // host (the dev box listens on 127.0.0.1 by default but
      // binding 0.0.0.0 here makes `make dev-frontend` work
      // when accessed from another machine on the LAN, e.g.
      // from a phone testing the Tauri Android wrapper).
      host: true,
      port: 1420,
      // Proxy /api and /uploads to the backend so the SPA can
      // fetch with relative paths inside Docker. When running
      // on the host without compose, the default 127.0.0.1:55245
      // matches the backend started by `make dev-backend`.
      //
      // The changeOrigin flag rewrites the Host header — matters
      // for OpenRouter / LLMs that 404 on unknown Host values.
      // secure: false avoids TLS cert errors when the proxy
      // target is plain HTTP.
      proxy: {
        '/api': {
          changeOrigin: true,
          secure: false,
          target: apiProxy,
        },
        '/uploads': {
          changeOrigin: true,
          secure: false,
          target: apiProxy,
        },
      },
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
  };
});
