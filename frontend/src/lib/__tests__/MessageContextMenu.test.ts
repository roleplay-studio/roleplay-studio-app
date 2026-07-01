import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Message } from '../api';

import MessageContextMenu from '../MessageContextMenu.svelte';

const fakeMsg: Message = {
  branch_group: null,
  branch_index: 0,
  content: 'Hello, world!',
  created_at: '2026-06-04T12:00:00Z',
  id: 1,
  is_active: true,
  role: 'assistant',
  short_content: '',
};

describe('MessageContextMenu', () => {
  beforeEach(() => {
    // jsdom doesn't expose navigator.clipboard by default.
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('does not render when position is null', () => {
    const { container } = render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose: vi.fn(), position: null },
    });
    expect(container.querySelector('.ctx-menu')).toBeNull();
  });

  it('renders Copy and Edit items when position is set', () => {
    const { container } = render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose: vi.fn(), position: { x: 100, y: 100 } },
    });
    const items = container.querySelectorAll('.ctx-item');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(/copy/i);
    expect(items[1]).toHaveTextContent(/edit/i);
  });

  it('Copy writes msg.content to the clipboard', async () => {
    render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose: vi.fn(), position: { x: 100, y: 100 } },
    });
    const copyBtn = screen.getByText(/^copy$/i);
    await fireEvent.click(copyBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello, world!');
  });

  it('Copy shows "Copied!" feedback and reverts after ~1.5s', async () => {
    vi.useFakeTimers();
    render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose: vi.fn(), position: { x: 100, y: 100 } },
    });
    const copyBtn = screen.getByText(/^copy$/i);
    await fireEvent.click(copyBtn);
    expect(screen.getByText(/^copied!$/i)).toBeInTheDocument();
    vi.advanceTimersByTime(1600);
    // Let Svelte flush the reactive update triggered by `copied = false`.
    await Promise.resolve();
    expect(screen.queryByText(/^copied!$/i)).toBeNull();
    vi.useRealTimers();
  });

  it('Edit invokes onedit with the msg and calls onclose', async () => {
    const onedit = vi.fn();
    const onclose = vi.fn();
    render(MessageContextMenu, {
      props: {
        msg: fakeMsg,
        onclose,
        onedit,
        position: { x: 100, y: 100 },
      },
    });
    const editBtn = screen.getByText(/^edit$/i);
    await fireEvent.click(editBtn);
    expect(onedit).toHaveBeenCalledWith(fakeMsg);
    expect(onclose).toHaveBeenCalled();
  });

  it('Esc key calls onclose', async () => {
    const onclose = vi.fn();
    render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose, position: { x: 100, y: 100 } },
    });
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).toHaveBeenCalled();
  });

  it('outside click calls onclose', async () => {
    const onclose = vi.fn();
    render(MessageContextMenu, {
      props: { msg: fakeMsg, onclose, position: { x: 100, y: 100 } },
    });
    // Component listens to mousedown (capture) so right-click release
    // after the menu mount doesn't re-close it via click. Use mouseDown
    // to simulate the same capture-phase dismissal path.
    await fireEvent.mouseDown(document.body);
    expect(onclose).toHaveBeenCalled();
  });
});
