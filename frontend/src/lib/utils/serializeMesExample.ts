// serializeMesExample.ts — inverse of parseMesExample. Frontend-only,
// display/edit helper. Used when the user edits dialogues in the visual
// editor and we need to persist the result back to the raw V2 string.

import type { MesExampleDialogue } from './parseMesExample';

// Canonical marker form. The serializer always normalizes to lowercase
// `{{user}}` / `{{char}}` even if the user originally imported the card
// with `<user>:` or `<bot>:` markers.
const MARKER = { char: '{{char}}: ', user: '{{user}}: ' } as const;

export function serializeMesExample(dialogues: MesExampleDialogue[]): string {
  if (!dialogues || dialogues.length === 0) return '';

  return dialogues
    .map((d) => {
      const body = d.turns.map((t) => `${MARKER[t.role]}${t.content}`).join('\n');
      return `<START>\n${body}\n<END>`;
    })
    .join('\n\n');
}
