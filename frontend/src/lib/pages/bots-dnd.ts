/**
 * Pure helpers for the BotsPage drag-and-drop zone.
 *
 * Kept separate from BotsPage.svelte so they can be unit-tested without
 * rendering the whole page (and the fetch / i18n / router graph that
 * implies). The component just imports these and uses them.
 */

export const SUPPORTED_BOT_FILE_EXTS = ['.jpeg', '.jpg', '.json', '.png', '.webp'] as const;

export type SupportedBotFileExt = (typeof SUPPORTED_BOT_FILE_EXTS)[number];

/**
 * Extract the lowercased file extension (including the leading dot).
 * Returns `''` for files without an extension.
 *
 * @example
 *   fileExt('Card.PNG') // '.png'
 *   fileExt('README')   // ''
 */
export function fileExt(name: string): string {
  const dot = name.lastIndexOf('.');
  if (dot <= 0 || dot === name.length - 1) return '';
  return '.' + name.slice(dot + 1).toLowerCase();
}

/** True if the file name is a supported bot card / character card format. */
export function isSupportedBotFile(name: string): boolean {
  return (SUPPORTED_BOT_FILE_EXTS as readonly string[]).includes(fileExt(name));
}
