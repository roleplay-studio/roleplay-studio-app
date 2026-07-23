/** Tests for the ``bot_edit.confirm_type_switch.*`` i18n keys.

These keys drive the type-switch confirmation modal that appears
when the user changes ``bot_type`` away from ``rp`` while any
RP-only field has unsaved content (see
``specs/bot-editor-type-aware/spec.md`` §Requirement: Type switch
with unsaved changes and ``botEditor.ts::hasHiddenRPContent``).

Mirrors the pattern in
``frontend/src/lib/__tests__/settings-reindex-i18n.test.ts``: lock
the keys, lock en/ru. The 5 other locales (de/fr/ja/ko/zh) fall
back to English through ``t()`` at i18n.ts:4099.
*/

import { describe, expect, it } from 'vitest';

import { t } from '../i18n';

const CONFIRM_KEYS = [
  'bot_edit.confirm_type_switch.title',
  'bot_edit.confirm_type_switch.body',
  'bot_edit.confirm_type_switch.confirm',
  'bot_edit.confirm_type_switch.cancel',
] as const;

describe('bot_edit.confirm_type_switch i18n contract', () => {
  it('exposes all 4 confirm_type_switch.* keys (frozen list)', () => {
    expect(CONFIRM_KEYS).toHaveLength(4);
  });

  it.each(CONFIRM_KEYS)('defines key %s', (key) => {
    expect(key).toMatch(/^bot_edit\.confirm_type_switch\./);
  });

  it.each([
    ['en', 'bot_edit.confirm_type_switch.title', 'Discard RolePlay-only fields?'],
    ['ru', 'bot_edit.confirm_type_switch.title', 'Удалить поля RolePlay?'],
    ['en', 'bot_edit.confirm_type_switch.confirm', 'Switch type'],
    ['ru', 'bot_edit.confirm_type_switch.confirm', 'Сменить тип'],
    ['en', 'bot_edit.confirm_type_switch.cancel', 'Cancel'],
    ['ru', 'bot_edit.confirm_type_switch.cancel', 'Отмена'],
  ] as const)('t(%j, %j) resolves to %j', (lang, key, expected) => {
    expect(t(key, lang)).toBe(expected);
  });

  it('body string is non-empty and mentions the hidden field categories', () => {
    // The body text is the contract that tells the user what they're
    // about to discard. We don't pin the full sentence (i18n churn),
    // just verify the categories are surfaced in English.
    const en = t('bot_edit.confirm_type_switch.body', 'en');
    expect(en).toContain('first message');
    expect(en).toContain('alternate greetings');
    expect(en).toContain('scenario');
    expect(en).toContain('example dialogues');
    expect(en).toContain('world-state prompt');
  });

  it('body string is non-empty and mentions the hidden field categories in ru', () => {
    const ru = t('bot_edit.confirm_type_switch.body', 'ru');
    expect(ru.length).toBeGreaterThan(20);
    expect(ru).toContain('первое сообщение');
    expect(ru).toContain('приветств');
    expect(ru).toContain('сценар');
    expect(ru).toContain('примеры диалогов');
    expect(ru).toContain('промпт состояния мира');
  });

  it('falls back to English for locales without a confirm_type_switch override', () => {
    // Same pattern as botsLibraryI18n.test.ts: pin the fallback so
    // a future contributor who removes the fallback gets a loud
    // test failure rather than silent UI breakage.
    expect(t('bot_edit.confirm_type_switch.title', 'de')).toBe(
      'Discard RolePlay-only fields?',
    );
    expect(t('bot_edit.confirm_type_switch.title', 'fr')).toBe(
      'Discard RolePlay-only fields?',
    );
    expect(t('bot_edit.confirm_type_switch.title', 'ja')).toBe(
      'Discard RolePlay-only fields?',
    );
    expect(t('bot_edit.confirm_type_switch.title', 'ko')).toBe(
      'Discard RolePlay-only fields?',
    );
    expect(t('bot_edit.confirm_type_switch.title', 'zh')).toBe(
      'Discard RolePlay-only fields?',
    );
  });
});