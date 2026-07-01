/**
 * Helpers for the bot editor's unified Greetings list.
 *
 * The UI shows a single tab list that holds both the bot's first
 * message (index 0) and any alternate greetings (index 1..N-1). When
 * the form is saved we split it back into the two API fields
 * (``first_message`` and ``alternate_greetings``). When loading a
 * bot, we stitch them back into one list.
 */

/** Stitch the two API fields into a single editor list. */
export function loadGreetings(
  firstMessage: string,
  alternateGreetings: readonly string[],
): string[] {
  return [firstMessage, ...alternateGreetings];
}

/** Split the editor list into the two API fields. */
export function saveGreetings(greetings: readonly string[]): {
  alternate_greetings: string[];
  first_message: string;
} {
  if (greetings.length === 0) {
    return { alternate_greetings: [], first_message: '' };
  }
  return {
    alternate_greetings: greetings.slice(1),
    first_message: greetings[0],
  };
}

/** Hard cap on total greetings (first + alternates). */
export const MAX_GREETINGS = 10;

/** Can the greeting at ``index`` move in the given direction? */
export function canSortGreeting(index: number, direction: 'down' | 'up', total: number): boolean {
  if (direction === 'up') return index > 0;
  return index < total - 1;
}

/** Swap a greeting with its neighbour in the given direction. */
export function sortGreeting<T>(
  greetings: readonly T[],
  index: number,
  direction: 'down' | 'up',
): T[] {
  const next = [...greetings];
  const target = direction === 'up' ? index - 1 : index + 1;
  if (target < 0 || target >= next.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
