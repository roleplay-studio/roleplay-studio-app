// parseMesExample.ts — parse a V1/V2/V3 character card `mes_example` field
// into structured dialogues for the BotEditPage visual editor.
//
// Frontend-only, display-only. The raw V2 string is always the source of
// truth on the backend. The parser is best-effort: a round-trip through
// the visual editor may normalize exotic markers to the canonical
// `{{user}}:` / `{{char}}:` form.

export interface MesExampleDialogue {
  turns: MesExampleTurn[];
}

export interface MesExampleTurn {
  content: string;
  role: 'char' | 'user';
}

// Recognizes role markers used in V1/V2/V3 character cards:
//   {{user}}: / {{char}}:    (V2 spec — no colon inside `{{ }}`, so the
//                              colon is captured separately)
//   <user>: / <bot>: / <char>:  (V1 / some card authors — colon is part
//                              of the marker)
// (case-insensitive). The first matching prefix starts a new turn.
const TURN_REGEX = /^(\{\{user\}\}:|\{\{char\}\}:|<user>:|<bot>:|<char>:)\s*/i;

// Captures one or more <START>...<END> blocks (non-greedy).
// Falls back to matching <START> up to the next <START> (or EOF)
// when the author forgot the closing <END> tag — some character
// card editors export the body with only the opening marker. The
// trailing <START> is re-included via ``lastIndex`` backtracking so
// the outer while-loop picks it up as the next block's head.
const BLOCK_REGEX = /<START>([\s\S]*?)(?:<END>|(?=<START>)|$)/g;

export function parseMesExample(raw: string): MesExampleDialogue[] {
  if (!raw || !raw.trim()) return [];

  const dialogues: MesExampleDialogue[] = [];

  // Reset regex state — global regexes carry lastIndex between calls.
  BLOCK_REGEX.lastIndex = 0;

  let match: null | RegExpExecArray;
  while ((match = BLOCK_REGEX.exec(raw)) !== null) {
    let blockBody = match[1];
    // Normalize Windows line endings first — character cards exported
    // from Windows tools sometimes carry \r\n. Splitting on \n would
    // leak stray \r into turn content; trim regexes below operate on
    // \n, so \r needs to be gone before they run.
    blockBody = blockBody.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    // Trim a single leading/trailing newline (the V2 spec's standard
    // format is `<START>\n...body...\n<END>`). Preserves interior newlines.
    blockBody = blockBody.replace(/^\n/, '').replace(/\n$/, '');
    const lines = blockBody.split('\n');
    const turns: MesExampleTurn[] = [];
    let currentRole: 'char' | 'user' | null = null;
    let currentLines: string[] = [];

    const flush = () => {
      if (currentRole && currentLines.length > 0) {
        turns.push({ content: currentLines.join('\n'), role: currentRole });
      }
      currentRole = null;
      currentLines = [];
    };

    for (const line of lines) {
      const turnMatch = line.match(TURN_REGEX);
      if (turnMatch) {
        flush();
        const marker = turnMatch[1].toLowerCase();
        currentRole =
          marker.startsWith('{{user}}') || marker.startsWith('<user>') ? 'user' : 'char';
        currentLines = [line.slice(turnMatch[0].length)];
      } else if (currentRole) {
        // Continuation line — join to the current turn's content.
        currentLines.push(line);
      }
      // Lines outside any turn (before the first marker) are ignored.
    }
    flush();

    if (turns.length > 0) {
      dialogues.push({ turns });
    }
  }

  return dialogues;
}
