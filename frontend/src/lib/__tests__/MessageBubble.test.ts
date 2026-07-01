import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Message } from '../api';

import MessageBubble from '../MessageBubble.svelte';

function msg(id: number, role: 'assistant' | 'user', content = '', isActive = true): Message {
  return {
    branch_group: 'g-' + id,
    branch_index: 0,
    content,
    created_at: null,
    id,
    is_active: isActive,
    reasoning: '',
    role,
    short_content: '',
    versions: [],
  };
}

const baseProps = {
  botName: 'B',
  isLast: false,
  lang: 'en' as const,
  personaName: 'U',
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('MessageBubble versions counter', () => {
  it('renders version counter on assistant bubble when versions > 1', () => {
    // v1 inactive (original), v2 active (edit). The bubble is v2.
    const v1 = { ...msg(10, 'assistant', 'first reply'), is_active: false };
    const v2 = msg(11, 'assistant', 'second reply', true);

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(11, 'assistant', 'second reply', true),
        onswitchversion: vi.fn(),
        versions: [v1, v2],
      },
    });

    // currentVersionIndex = 1 (v2 is active), totalVersions = 2
    expect(screen.getByText('2/2')).toBeTruthy();
  });

  it('renders version counter on user bubble when versions > 1', () => {
    // Same shape as the assistant case but for user role — this is
    // the bug we are fixing: user bubbles did not have the counter.
    const v1 = { ...msg(20, 'user', 'original'), is_active: false };
    const v2 = msg(21, 'user', 'edited', true);

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(21, 'user', 'edited', true),
        onedit: vi.fn(),
        onswitchversion: vi.fn(),
        versions: [v1, v2],
      },
    });

    // currentVersionIndex = 1 (v2 is active), totalVersions = 2
    expect(screen.getByText('2/2')).toBeTruthy();
  });

  it('does NOT render version counter when versions = 1', () => {
    const only = msg(30, 'assistant', 'only one', true);

    const { container } = render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(30, 'assistant', 'only one', true),
        versions: [only],
      },
    });

    expect(container.querySelector('.mb-versions')).toBeNull();
    expect(screen.queryByText('1/1')).toBeNull();
  });

  it('does NOT render version counter when versions = [] (default)', () => {
    const { container } = render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(40, 'user', 'no branch', true),
        versions: [],
      },
    });

    expect(container.querySelector('.mb-versions')).toBeNull();
  });

  it('calls onswitchversion with previous version id on prev click', async () => {
    // Bubble is the active v1 (index 0). Clicking prev should be
    // disabled (canGoPrev = false because currentIndex = 0). So we
    // need the active version to be in the middle.
    const v1 = { ...msg(50, 'assistant', 'v1'), is_active: false };
    const v2 = msg(51, 'assistant', 'v2', true);
    const v3 = { ...msg(52, 'assistant', 'v3'), is_active: false };
    const onSwitch = vi.fn();

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(51, 'assistant', 'v2', true),
        onswitchversion: onSwitch,
        versions: [v1, v2, v3],
      },
    });

    // currentVersionIndex = 1 (v2 active). prev should call v1.
    const prevBtn = screen.getByLabelText('Previous version');
    expect(prevBtn).toBeTruthy();
    // The component should not be disabled (v2 is not the first)
    await prevBtn.click();
    expect(onSwitch).toHaveBeenCalledWith(50);
  });

  it('calls onswitchversion with next version id on next click', async () => {
    const v1 = msg(60, 'assistant', 'v1', true);
    const v2 = { ...msg(61, 'assistant', 'v2'), is_active: false };
    const v3 = { ...msg(62, 'assistant', 'v3'), is_active: false };
    const onSwitch = vi.fn();

    render(MessageBubble, {
      props: {
        ...baseProps,
        msg: msg(60, 'assistant', 'v1', true),
        onswitchversion: onSwitch,
        versions: [v1, v2, v3],
      },
    });

    // currentVersionIndex = 0 (v1 active). next should call v2.
    const nextBtn = screen.getByLabelText('Next version');
    expect(nextBtn).toBeTruthy();
    await nextBtn.click();
    expect(onSwitch).toHaveBeenCalledWith(61);
  });
});
