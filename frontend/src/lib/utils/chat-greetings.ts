import type { Message } from '../api';

/**
 * Returns messages as they should be rendered in the chat, with the
 * currently-selected greeting overlaid onto the first assistant bubble
 * — but only while the user has not yet spoken.
 *
 * When the user types their first message, the greeting is locked in:
 * we stop overlaying, so the bubble shows whatever is persisted in the
 * DB.
 *
 * Rules:
 * - If `greetingIndex` is out of range → return the original messages
 *   unchanged (defensive: caller may have a stale index).
 * - If the user has already spoken (`messages.some(m => m.role === 'user')`)
 *   → return the original messages unchanged (the greeting is now anchored
 *   to the conversation, the user's first send persisted it via
 *   `api.updateMessage`).
 * - Otherwise → find the first non-system message (typically the
 *   auto-saved first_message) and replace its `content` with the chosen
 *   greeting. The message's `id` and other fields are preserved so
 *   the bubble keeps the same identity in the DOM/keyed each block.
 */
export function displayedMessages(
  messages: Message[],
  greetings: string[],
  greetingIndex: number,
): Message[] {
  if (greetingIndex < 0 || greetingIndex >= greetings.length) return messages;
  // Lock the greeting the moment the user speaks.
  if (messages.some((m) => m.role === 'user')) return messages;
  // Find the first non-system message (typically the auto-saved first_message).
  const idx = messages.findIndex((m) => m.role !== 'system');
  if (idx === -1) return messages;
  const greeting = greetings[greetingIndex];
  if (!greeting) return messages;
  const next = messages.slice();
  next[idx] = { ...next[idx], content: greeting };
  return next;
}

/**
 * Is the greeting switcher locked for the current thread?
 *
 * The switcher lets the user cycle through `bot.first_message` and
 * `bot.alternate_greetings` BEFORE the conversation starts. It must
 * stay visible (and meaningful) as long as the user has not yet said
 * anything — even though the assistant's first message has already
 * been auto-persisted to the DB by ChatService._build_request.
 *
 * Locking condition: there is at least one user message in the thread.
 *
 * Returns false for an empty thread, a system-only thread, or a thread
 * that contains only the auto-saved first_message. Returns true as soon
 * as the user has spoken.
 */
export function isGreetingLocked(messages: Message[]): boolean {
  return messages.some((m) => m.role === 'user');
}
