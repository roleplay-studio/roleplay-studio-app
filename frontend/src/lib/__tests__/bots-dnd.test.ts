import { describe, expect, it } from 'vitest';

import { fileExt, isSupportedBotFile, SUPPORTED_BOT_FILE_EXTS } from '../pages/bots-dnd';

describe('bots-dnd helpers', () => {
  describe('fileExt', () => {
    it('returns the lowercased extension with leading dot', () => {
      expect(fileExt('card.PNG')).toBe('.png');
      expect(fileExt('foo.json')).toBe('.json');
      expect(fileExt('Mixed.WebP')).toBe('.webp');
    });

    it('returns "" for files without an extension', () => {
      expect(fileExt('README')).toBe('');
      expect(fileExt('')).toBe('');
    });

    it('returns "" when the dot is the first character (hidden file)', () => {
      expect(fileExt('.gitignore')).toBe('');
    });
  });

  describe('SUPPORTED_BOT_FILE_EXTS', () => {
    it('includes the five formats that GlobalDropZone accepts', () => {
      expect([...SUPPORTED_BOT_FILE_EXTS].sort()).toEqual([
        '.jpeg',
        '.jpg',
        '.json',
        '.png',
        '.webp',
      ]);
    });
  });

  describe('isSupportedBotFile', () => {
    it.each([
      ['character-card.png', true],
      ['Card.PNG', true],
      ['bot.json', true],
      ['avatar.webp', true],
      ['photo.jpeg', true],
      ['photo.jpg', true],
    ])('accepts %s', (name, expected) => {
      expect(isSupportedBotFile(name)).toBe(expected);
    });

    it.each([
      ['document.pdf', false],
      ['archive.zip', false],
      ['README', false],
      ['no-extension', false],
      ['card.gif', false],
    ])('rejects %s', (name, expected) => {
      expect(isSupportedBotFile(name)).toBe(expected);
    });
  });
});
