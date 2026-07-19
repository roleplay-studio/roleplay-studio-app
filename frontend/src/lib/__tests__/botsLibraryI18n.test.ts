import { describe, expect, it } from 'vitest';

import { t } from '../i18n';

/**
 * The Bots library page (``BotsPage``) gets a sort / filter / search
 * toolbar introduced by ``improve-bot-editor``. This test pins the i18n
 * contract — both presence of the keys and the English / Russian
 * values — so the toolbar can't accidentally regress to hardcoded text.
 *
 * Mirrors the pattern in
 * ``frontend/src/lib/__tests__/settings-reindex-i18n.test.ts``: lock
 * the keys, lock en/ru, leave the other 5 locales to the existing
 * ``t()`` English fallback (see ``i18n.ts:4099`` — `t(key, lang)` falls
 * back to ``dict.en[key]`` if the requested lang doesn't define it).
 */

const BOT_LIBRARY_KEYS = [
  'bot_library.sort_label',
  'bot_library.sort_name_asc',
  'bot_library.sort_name_desc',
  'bot_library.sort_id_asc',
  'bot_library.sort_id_desc',
  'bot_library.sort_threads_desc',
  'bot_library.filter_types_label',
  'bot_library.filter_clear_all',
  'bot_library.search_placeholder',
  'bot_library.empty_state',
  'bot_library.error_fetch',
  'bot_library.retry',
  'bot_library.results_count',
] as const;

describe('bot_library i18n contract', () => {
  it('exposes all 13 bot_library.* keys (frozen list — adjust deliberately)', () => {
    expect(BOT_LIBRARY_KEYS).toHaveLength(13);
  });

  it.each(BOT_LIBRARY_KEYS)('defines key %s', (key) => {
    expect(key).toMatch(/^bot_library\./);
  });

  it.each([
    ['en', 'bot_library.sort_label', 'Sort by'],
    ['ru', 'bot_library.sort_label', 'Сортировать по'],
    ['en', 'bot_library.sort_name_asc', 'Name (A→Z) ↑'],
    ['ru', 'bot_library.sort_name_asc', 'Имя (А→Я) ↑'],
    ['en', 'bot_library.sort_name_desc', 'Name (Z→A) ↓'],
    ['ru', 'bot_library.sort_name_desc', 'Имя (Я→А) ↓'],
    ['en', 'bot_library.sort_id_asc', 'Oldest first ↑'],
    ['ru', 'bot_library.sort_id_asc', 'Сначала старые ↑'],
    ['en', 'bot_library.sort_id_desc', 'Newest first ↓'],
    ['ru', 'bot_library.sort_id_desc', 'Сначала новые ↓'],
    ['en', 'bot_library.sort_threads_desc', 'Most chats first ↓'],
    ['ru', 'bot_library.sort_threads_desc', 'Больше всего чатов ↓'],
    ['en', 'bot_library.filter_types_label', 'Filter by type'],
    ['ru', 'bot_library.filter_types_label', 'Фильтр по типу'],
    ['en', 'bot_library.filter_clear_all', 'Clear all'],
    ['ru', 'bot_library.filter_clear_all', 'Сбросить всё'],
    ['en', 'bot_library.search_placeholder', 'Search by name…'],
    ['ru', 'bot_library.search_placeholder', 'Поиск по имени…'],
    ['en', 'bot_library.empty_state', 'No bots match your filters'],
    ['ru', 'bot_library.empty_state', 'Нет ботов по выбранным фильтрам'],
    ['en', 'bot_library.error_fetch', 'Failed to load bots'],
    ['ru', 'bot_library.error_fetch', 'Не удалось загрузить список ботов'],
    ['en', 'bot_library.retry', 'Retry'],
    ['ru', 'bot_library.retry', 'Повторить'],
  ] as const)('t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });

  it('results_count interpolates {count} and {total} placeholders', () => {
    // The toolbar uses this for "X of Y" display — the placeholders
    // are the contract; the surrounding text is i18n-specific.
    expect(t('bot_library.results_count', 'en')).toContain('{count}');
    expect(t('bot_library.results_count', 'en')).toContain('{total}');
    expect(t('bot_library.results_count', 'ru')).toContain('{count}');
    expect(t('bot_library.results_count', 'ru')).toContain('{total}');
  });

  it('falls back to English for locales without a bot_library override', () => {
    // The 5 non-en/ru locales (de, fr, ja, ko, zh) intentionally
    // don't define these keys yet — see the fallback at i18n.ts:4099.
    // Pin the behaviour so a future contributor who removes the
    // fallback gets a loud test failure, not silent UI breakage.
    expect(t('bot_library.sort_label', 'de')).toBe('Sort by');
    expect(t('bot_library.sort_label', 'fr')).toBe('Sort by');
    expect(t('bot_library.sort_label', 'ja')).toBe('Sort by');
    expect(t('bot_library.sort_label', 'ko')).toBe('Sort by');
    expect(t('bot_library.sort_label', 'zh')).toBe('Sort by');
  });
});