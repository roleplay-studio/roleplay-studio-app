/**
 * Shared rune-based state for the SetupWizard.
 *
 * Single deep-reactive `$state` object that the orchestrator and all 8 step
 * components read and write. Property access (`wizardState.apiKey = 'x'`) is
 * reactive in Svelte 5 — components that read `wizardState.apiKey` re-render
 * automatically when it changes.
 *
 * This object replaces the 25 separate `let X = $state(...)` declarations
 * that used to live in SetupWizard.svelte. The semantics are identical; the
 * import shape is simpler.
 */

import { detectBrowserLang } from '../../i18n';

export interface Provider {
  default_base_url: string;
  default_model: string;
  description: string;
  id: string;
  label: string;
  manual_setup: boolean;
  needs_key: boolean;
}

/**
 * Phase 1.5a: the backend now wraps the catalog list in an object
 * so the wizard can restore the user's prior provider choice on
 * reload. See `api/routes/setup.py::list_providers`.
 */
export interface ProvidersResponse {
  providers: Provider[];
  selected_provider: string;
}

export interface LangOption {
  id: string;
  label: string;
}

export interface StarterBot {
  id: string;
  name: string;
  format: string;
  first_message: string;
  scenario: string;
  personality: string;
  categories: string[];
  avatar_data_url: string;
  error?: string;
}

export const wizardState = $state({
  // Step index
  step: 0,
  maxStep: 7,

  // Provider/model data (loaded from /api/setup/providers on mount)
  providers: [] as Provider[],
  languages: [] as LangOption[],
  selectedProvider: 'openrouter',

  // Form fields
  baseUrl: '',
  apiKey: '',
  chatModel: '',
  customModel: '',
  editFastModel: '',
  // Seeded from browser locale (see i18n.detectBrowserLang) so first-run
  // users land in their own language; the orchestrator syncs this back to
  // `currentLang` via $effect once the wizard mounts.
  editLanguage: detectBrowserLang(),
  editTheme: 'system',
  personaName: '',
  personaDescription: '',
  enableRag: false,
  embeddingModel: '',
  embeddingBaseUrl: '',
  embeddingApiKey: '',

  // Starter-bot picker (StepFinish). Loaded once on mount, never re-fetched.
  starterBots: [] as StarterBot[],
  selectedStarterBotIds: [] as string[],
  // Filled by saveAll() — shown on the success screen.
  importedStarterBots: [] as Array<{ id: string; bot_id: number; name: string }>,
  failedStarterBots: [] as Array<{ id: string; reason: string }>,

  // UI state
  loading: false,
  error: '',
  done: false,
  dataLoading: true,
  validating: false,
  validated: null as boolean | null,
  validatingRag: false,
  savedPersonaName: '',
});
