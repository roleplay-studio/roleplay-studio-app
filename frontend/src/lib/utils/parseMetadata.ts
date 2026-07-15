import yaml from 'js-yaml';

export interface MetadataEntry {
  displayKey: string;
  isNumeric: boolean;
  key: string;
  value: number | string;
}

export interface ParsedMessage {
  actions: null | string[];
  mainContent: string;
  notification: null | string;
  stats: MetadataEntry[] | null;
}

export function parseMessageContent(content: string): ParsedMessage {
  const sepIndex = findSeparator(content);

  if (sepIndex < 0) {
    return { actions: null, mainContent: content, notification: null, stats: null };
  }

  // Compute the slice boundary dynamically — sepIndex may point
  // at start-of-content (0) or at a `\n` before the `---` line.
  // We need to skip the `---` line itself before reading metaText.
  const afterSep = content.slice(sepIndex);
  const dashMatch = afterSep.match(/---[ \t]*/);
  const dashEnd = dashMatch ? dashMatch.index! + dashMatch[0].length : 0;
  const mainContent = content.slice(0, sepIndex).replace(/\n$/, '');
  const metaText = afterSep.slice(dashEnd).replace(/^\n+/, '').trim();
  if (!metaText) {
    return { actions: null, mainContent, notification: null, stats: null };
  }

  // LLM models often emit metadata followed by a closing `---`
  // sentinel (with or without surrounding blank lines) to
  // visually mark the end of the block. `js-yaml` interprets a
  // bare `---` line as a document separator and throws
  // "expected a single document in the stream, but found more"
  // when it appears after a mapping/sequence, which kicks the
  // whole block into the plain-text notification fallback.
  //
  // Strip a trailing `---` line ONLY when nothing real follows
  // it — if there is content after the sentinel, leaving the
  // `---` in place lets the fallback chain handle it (we'd
  // rather show a notification than silently drop user-visible
  // text). The stripped text is used for every branch (YAML,
  // JSON, kv, bullets, notification) so the contract is
  // consistent: `---` at the end of metadata is always noise.
  const metaTextForParsing = stripTrailingYamlSentinel(metaText);

  // 0. Try YAML (primary format). Only short-circuit on object
  // (mapping → stats) and array (sequence → actions). When YAML
  // returns a string or null/undefined, fall through to the
  // existing JSON / kv / bullets / notification chain.
  let yamlParsed: unknown = undefined;
  try {
    yamlParsed = yaml.load(metaTextForParsing);
  } catch {
    // not valid YAML — fall through
  }

  if (yamlParsed && typeof yamlParsed === 'object' && !Array.isArray(yamlParsed)) {
    const entries: MetadataEntry[] = [];
    for (const [k, v] of Object.entries(yamlParsed as Record<string, unknown>)) {
      if (v === null || v === undefined) continue;
      const isNum = typeof v === 'number';
      entries.push({
        displayKey: String(k).charAt(0).toUpperCase() + String(k).slice(1),
        isNumeric: isNum,
        key: String(k).toLowerCase(),
        value: isNum ? (v as number) : String(v),
      });
    }
    if (entries.length > 0) {
      return { actions: null, mainContent, notification: null, stats: entries };
    }
  }

  if (Array.isArray(yamlParsed) && yamlParsed.length > 0) {
    const actions = yamlParsed.filter((v) => v !== null && v !== undefined).map((v) => String(v));
    if (actions.length > 0) {
      return { actions, mainContent, notification: null, stats: null };
    }
  }

  // 1. Try JSON
  try {
    const obj = JSON.parse(metaTextForParsing);
    if (typeof obj === 'object' && obj !== null && !Array.isArray(obj)) {
      const entries = Object.entries(obj).map(([key, val]) => ({
        displayKey: key.charAt(0).toUpperCase() + key.slice(1),
        isNumeric: typeof val === 'number',
        key: key.toLowerCase(),
        value: typeof val === 'number' ? val : String(val ?? ''),
      }));
      return {
        actions: null,
        mainContent,
        notification: null,
        stats: entries.length > 0 ? entries : null,
      };
    }
  } catch {
    // not JSON
  }

  // 2. Try key:value lines
  const lines = metaTextForParsing.split('\n');
  const entries: MetadataEntry[] = [];
  let allKeyValue = true;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const match = trimmed.match(/^([\w\s-]+?)\s*[:=]\s*(.+)$/);
    if (match) {
      const key = match[1].trim();
      const rawVal = match[2].trim();
      const numVal = Number(rawVal);
      const value = !isNaN(numVal) && rawVal.length > 0 ? numVal : rawVal;
      entries.push({
        displayKey: key,
        isNumeric: typeof value === 'number',
        key: key.toLowerCase(),
        value,
      });
    } else {
      allKeyValue = false;
      break;
    }
  }

  if (entries.length > 0 && allKeyValue) {
    return { actions: null, mainContent, notification: null, stats: entries };
  }

  // 3. Try bullet list (lines starting with "- " or "* " or "1. ")
  const actions: string[] = [];
  let allBullets = true;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const match = trimmed.match(/^[-*\d]+\.?\s+(.+)$/);
    if (match) {
      actions.push(match[1].trim());
    } else {
      allBullets = false;
      break;
    }
  }

  if (actions.length > 0 && allBullets) {
    return { actions, mainContent, notification: null, stats: null };
  }

  // 4. Plain text — notification
  return { actions: null, mainContent, notification: metaTextForParsing, stats: null };
}

// Structural separator: a line containing only '---' (with
// optional trailing whitespace) is the metadata boundary iff it
// is preceded by a blank line (or sits at column 0 of the
// content) and followed by another newline.
//
// Why blank lines: markdown `---` (hr, setext underline) uses
// the same three hyphens. An hr/setext underline glued to other
// text shouldn't get eaten as a metadata divider.
//
// Backward compat: we ALSO match the legacy single-newline
// format `\n---\n` (no blank line required) so existing chat
// history keeps parsing. The blank-line form takes priority
// when both are present.
//
// Returns the index in `content` where the metadata block
// starts. Callers slice `[0, sepIndex]` for the body.
// Returns -1 if no separator.
function findSeparator(content: string): number {
  // 1. Preferred: blank-line form `\n\n---\n` (new format).
  const reBlank = /\n\n---\s*\n/g;
  let lastIdx = -1;
  for (const m of content.matchAll(reBlank)) {
    lastIdx = m.index! + 1;
  }
  if (lastIdx >= 0) return lastIdx;

  // 2. Legacy: single-newline form `\n---\n` (backward compat).
  const reLegacy = /\n---\n/g;
  for (const m of content.matchAll(reLegacy)) {
    lastIdx = m.index! + 1;
  }
  if (lastIdx >= 0) return lastIdx;

  // 3. Edge: --- at very start of content (no leading newline).
  if (content.startsWith('---\n') || content.startsWith('---\r\n')) {
    return 0;
  }

  // 4. Edge: --- at very end (no trailing content after it).
  const trimmedEnd = content.match(/\n\n---\s*$/);
  if (trimmedEnd && trimmedEnd.index !== undefined) {
    return trimmedEnd.index + 1;
  }
  // Legacy trailing form: content ends with `\n---` (no trailing newline).
  const legacyEnd = content.match(/\n---\s*$/);
  if (legacyEnd && legacyEnd.index !== undefined) {
    return legacyEnd.index + 1;
  }

  return -1;
}

// Strip a trailing `---` YAML document-separator line — but
// ONLY when nothing real follows it. If there is non-whitespace
// content after the `---`, the `---` is structurally a
// separator between metadata and the rest of the message, and
// we keep the entire string so the fallback chain can decide
// what to do (rather than silently dropping the trailing
// content).
function stripTrailingYamlSentinel(text: string): string {
  return text.replace(/\n+---\s*$/, '').replace(/\n*---\s*$/, '');
}
