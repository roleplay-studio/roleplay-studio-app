/// <reference types="svelte" />
/// <reference types="vite/client" />

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ImportMetaEnv {
  /**
   * Set to "true" when the app is served through the Vite dev
   * server's /api proxy (i.e. inside the docker-compose dev
   * stack). When unset, api.ts falls back to fetching the API
   * directly on 127.0.0.1:55245.
   */
  readonly VITE_USE_PROXY?: string;
}
