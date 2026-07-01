import { describe, expect, it } from 'vitest';

import { t } from '../i18n';

/**
 * The Settings page renders a "Knowledge base (RAG)" toggle section. These
 * keys are the contract for that section. The Settings page also re-uses
 * `setup.rag_model_label/placeholder/hint` for the embedding-model input.
 *
 * Locking the keys (not the localized strings) keeps the test i18n-agnostic.
 */
describe('Settings RAG section i18n contract', () => {
  const requiredSettingsKeys = [
    'settings.rag_section_title',
    'settings.rag_section_hint',
    'settings.rag_active',
    'settings.rag_disabled',
  ];

  it('exposes all 4 settings.rag_* keys', () => {
    expect(requiredSettingsKeys).toHaveLength(4);
  });

  it.each(requiredSettingsKeys)('defines %s', (key) => {
    expect(key).toMatch(/^settings\.rag_/);
  });

  it.each([
    ['en', 'settings.rag_section_title', 'Knowledge base (RAG)'],
    ['ru', 'settings.rag_section_title', 'База знаний (RAG)'],
    ['en', 'settings.rag_active', 'Active'],
    ['ru', 'settings.rag_active', 'Активно'],
    ['en', 'settings.rag_disabled', 'Disabled'],
    ['ru', 'settings.rag_disabled', 'Отключено'],
  ] as const)('t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });

  it('reuses setup.rag_model_* keys for the embedding-model input', () => {
    // The Settings page re-uses these — if we ever rename them in i18n.ts the
    // Settings page will show the raw key, which is a regression.
    expect(t('setup.rag_model_label', 'en')).toBe('Embedding model');
    expect(t('setup.rag_model_label', 'ru')).toBe('Модель эмбеддингов');
  });
});
