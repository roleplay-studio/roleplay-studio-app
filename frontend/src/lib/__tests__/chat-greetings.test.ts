import { describe, expect, it } from 'vitest';

import type { Message } from '../api';

import { displayedMessages, isGreetingLocked } from '../utils/chat-greetings';

function msg(role: 'assistant' | 'system' | 'user', id = 1, content = ''): Message {
  return {
    branch_group: null,
    branch_index: 0,
    content,
    created_at: null,
    id,
    is_active: true,
    reasoning: '',
    role,
    short_content: '',
  };
}

describe('isGreetingLocked', () => {
  it('returns false on an empty thread (no messages at all)', () => {
    // Edge case: thread was just created, listMessages not yet called.
    expect(isGreetingLocked([])).toBe(false);
  });

  it('returns false when only the auto-saved first_message is present', () => {
    // The first_message assistant bubble is persisted by
    // ChatService._build_request when the thread is created, BEFORE the
    // user has said anything. Switching greetings here is still meaningful
    // — the user is reading the greeting and deciding whether to start a
    // conversation.
    expect(isGreetingLocked([msg('assistant')])).toBe(false);
  });

  it('returns false for a system-only thread', () => {
    expect(isGreetingLocked([msg('system'), msg('system')])).toBe(false);
  });

  it('returns true once the user has sent at least one message', () => {
    expect(isGreetingLocked([msg('assistant', 1), msg('user', 2)])).toBe(true);
  });

  it('returns true even if the user message is the very first one (no assistant yet)', () => {
    // The user wrote first — the greeting switcher must lock, because
    // the assistant response is now anchored to a specific conversation
    // context.
    expect(isGreetingLocked([msg('user', 1)])).toBe(true);
  });
});

describe('displayedMessages', () => {
  const greetings = ['Hello world', 'Hi there', 'Howdy'];

  it('returns an empty array when there are no messages', () => {
    expect(displayedMessages([], greetings, 0)).toEqual([]);
  });

  it('overrides the first assistant message with the currently selected greeting', () => {
    // The user has NOT spoken yet — only the auto-saved first_message
    // is present. Switching greetings should overlay the selected text
    // onto that bubble.
    const msgs = [msg('assistant', 100, 'Hello world')];
    const result = displayedMessages(msgs, greetings, 2);
    expect(result[0].content).toBe('Howdy');
    expect(result[0].id).toBe(100); // identity preserved
  });

  it('does NOT override once the user has spoken', () => {
    const msgs = [msg('assistant', 100, 'Hello world'), msg('user', 101, 'hi')];
    const result = displayedMessages(msgs, greetings, 1);
    expect(result[0].content).toBe('Hello world'); // unchanged
  });

  it('does NOT override a system message at index 0', () => {
    const msgs = [msg('system', 100, 'ctx'), msg('assistant', 101, 'Hi')];
    const result = displayedMessages(msgs, greetings, 2);
    expect(result[0].content).toBe('ctx');
    expect(result[1].content).toBe('Howdy');
  });

  it('falls back to the original message if greetingIndex is out of range', () => {
    const msgs = [msg('assistant', 100, 'Hello world')];
    const result = displayedMessages(msgs, greetings, 99);
    expect(result[0].content).toBe('Hello world');
  });
});
