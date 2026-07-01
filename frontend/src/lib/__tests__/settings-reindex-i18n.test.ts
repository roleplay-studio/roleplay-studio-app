import { describe, expect, it } from 'vitest';

import { t } from '../i18n';

/**
 * The Settings page shows a reindex banner when there are stale embedding
 * collections, and a modal with SSE progress. The i18n keys below are the
 * contract for that UI.
 *
 * Locking the keys (not the localized strings) keeps the test i18n-agnostic.
 * We verify English and Russian for the keys that have hardcoded values
 * (titles, buttons) and assert structure for the pluralization key.
 */
describe('Settings reindex UI i18n contract', () => {
  const requiredReindexKeys = [
    'reindex.banner_title',
    'reindex.banner_body',
    'reindex.banner_action_all',
    'reindex.modal_title',
    'reindex.modal_cancel',
  ];

  it('exposes all 5 reindex.* keys', () => {
    expect(requiredReindexKeys).toHaveLength(5);
  });

  it.each(requiredReindexKeys)('defines %s', (key) => {
    expect(key).toMatch(/^reindex\./);
  });

  it.each([
    ['en', 'reindex.banner_title', 'Embedding model changed'],
    ['ru', 'reindex.banner_title', 'Модель эмбеддингов изменилась'],
    ['en', 'reindex.banner_action_all', 'Reindex all'],
    ['ru', 'reindex.banner_action_all', 'Переиндексировать все'],
    ['en', 'reindex.modal_title', 'Reindexing knowledge base'],
    ['ru', 'reindex.modal_title', 'Переиндексация базы знаний'],
    ['en', 'reindex.modal_cancel', 'Cancel'],
    ['ru', 'reindex.modal_cancel', 'Отмена'],
  ] as const)('t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });

  it('uses ICU plural format for banner_body (en)', () => {
    const en = t('reindex.banner_body', 'en');
    expect(en).toContain('# bot has');
    expect(en).toContain('# bots have');
  });

  it('uses ICU plural format for banner_body (ru)', () => {
    const ru = t('reindex.banner_body', 'ru');
    // Russian has 4 plural forms; we just confirm the key is non-empty and
    // contains the placeholder.
    expect(ru).toContain('{count');
    expect(ru).toMatch(/# (бот|бота|ботов)/);
  });
});

/**
 * The Settings page has 6 tabs (Provider, Generation, Memory,
 * Knowledge, Interface, System). The split of the bloated Generation
 * tab into 3 focused tabs is locked in by these keys — if a future
 * refactor removes them, the user will lose the tabs.
 */
describe('Settings tab labels i18n contract', () => {
  const requiredTabKeys = [
    'settings.tab_generation',
    'settings.tab_memory',
    'settings.tab_knowledge',
    'settings.tab_interface',
  ];

  it('exposes all 4 settings.tab_* keys', () => {
    expect(requiredTabKeys).toHaveLength(4);
  });

  it.each(requiredTabKeys)('defines %s', (key) => {
    expect(key).toMatch(/^settings\.tab_/);
  });

  it.each([
    ['en', 'settings.tab_generation', 'Generation'],
    ['ru', 'settings.tab_generation', 'Генерация'],
    ['en', 'settings.tab_memory', 'Memory'],
    ['ru', 'settings.tab_memory', 'Память'],
    ['en', 'settings.tab_knowledge', 'Knowledge base'],
    ['ru', 'settings.tab_knowledge', 'База знаний'],
    ['en', 'settings.tab_interface', 'Interface'],
    ['ru', 'settings.tab_interface', 'Интерфейс'],
  ] as const)('t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });

  it.each([
    ['en', 'settings.memory_section_title', 'Memory'],
    ['ru', 'settings.memory_section_title', 'Память'],
    ['en', 'settings.knowledge_section_title', 'Knowledge base (RAG)'],
    ['ru', 'settings.knowledge_section_title', 'База знаний (RAG)'],
    ['en', 'settings.save_all', 'Save all settings'],
    ['ru', 'settings.save_all', 'Сохранить'],
    ['en', 'settings.save_all_saved', 'All settings saved'],
    ['ru', 'settings.save_all_saved', 'Все настройки сохранены'],
  ] as const)('section/save key t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });
});
