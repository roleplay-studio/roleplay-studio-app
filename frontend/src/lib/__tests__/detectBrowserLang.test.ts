import { afterEach, describe, expect, it, vi } from 'vitest';

import { detectBrowserLang } from '../i18n';

/**
 * `detectBrowserLang()` reads `navigator.language` at module init / call time
 * and maps it to one of the supported `availableLangs()` ids. The vitest
 * environment is jsdom, so we mutate the global `navigator` to drive each
 * case rather than mocking the function under test.
 */
describe('detectBrowserLang', () => {
  const original = (navigator as any).language;

  afterEach(() => {
    Object.defineProperty(navigator, 'language', {
      configurable: true,
      value: original,
    });
  });

  function setLang(value: string | undefined) {
    Object.defineProperty(navigator, 'language', {
      configurable: true,
      value,
    });
  }

  it('returns the 2-letter prefix when the browser locale is a region variant', () => {
    setLang('ru-RU');
    expect(detectBrowserLang()).toBe('ru');
  });

  it('lowercases the language code', () => {
    setLang('DE');
    expect(detectBrowserLang()).toBe('de');
  });

  it('accepts a bare language code (no region)', () => {
    setLang('ja');
    expect(detectBrowserLang()).toBe('ja');
  });

  it('falls back to "en" when the browser language is not supported', () => {
    setLang('xx');
    expect(detectBrowserLang()).toBe('en');
  });

  it('falls back to "en" when navigator.language is empty', () => {
    setLang('');
    expect(detectBrowserLang()).toBe('en');
  });

  it('falls back to "en" when navigator is undefined (SSR / node)', async () => {
    const spy = vi.spyOn(globalThis, 'navigator', 'get');
    spy.mockReturnValue(undefined as any);
    try {
      expect(detectBrowserLang()).toBe('en');
    } finally {
      spy.mockRestore();
    }
  });
});
