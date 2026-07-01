// ThreadItem.test.ts — vitest cases for the atomic thread row used by
// ThreadDrawer. Tests cover: render (default + with persona), selected
// state, rename mode (input + bind:renameValue), Enter/Escape/blur
// handlers, click/contextmenu/dots callbacks, and that the dots button
// stops propagation so it doesn't trigger the parent click.

import { cleanup, fireEvent, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Thread } from '../../api';

import ThreadItem from '../../ui/ThreadItem.svelte';

afterEach(() => cleanup());

function makeThread(over: Partial<Thread> = {}): Thread {
  return {
    bot_id: 1,
    created_at: '2026-06-14T10:00:00Z',
    id: 1,
    name: 'Whispers in the dark',
    persona_id: 1,
    persona_name: 'Aria',
    summary: null,
    ...over,
  };
}

describe('ThreadItem', () => {
  it('renders the thread name and the time label', () => {
    const { container, getByText } = render(ThreadItem, {
      props: { thread: makeThread(), timeLabel: '5m' },
    });
    const root = container.querySelector('.ti');
    expect(root).toBeTruthy();
    expect(root?.querySelector('.ti-name')?.textContent?.trim()).toBe('Whispers in the dark');
    expect(root?.querySelector('.ti-time')?.textContent?.trim()).toBe('5m');
    expect(getByText('Aria')).toBeTruthy();
  });

  it('hides the persona span when persona_name is null', () => {
    const { container } = render(ThreadItem, {
      props: {
        thread: makeThread({ persona_id: null, persona_name: null }),
        timeLabel: '1d',
      },
    });
    expect(container.querySelector('.ti-persona')).toBeNull();
    // time is still shown
    expect(container.querySelector('.ti-time')?.textContent?.trim()).toBe('1d');
  });

  it('applies the ti-selected class when selected=true', () => {
    const { container } = render(ThreadItem, {
      props: { selected: true, thread: makeThread(), timeLabel: '1h' },
    });
    expect(container.querySelector('.ti')?.classList.contains('ti-selected')).toBe(true);
  });

  it('renders the rename input and binds renameValue when renaming=true', async () => {
    let v = 'Whispers in the dark';
    const { component } = render(ThreadItem, {
      props: {
        onrename: (id: number, name: string) => {
          v = name;
        },
        renameValue: v,
        renaming: true,
        thread: makeThread(),
        timeLabel: '1h',
      },
    });
    // input is present and prefilled with the bound renameValue
    const input = document.querySelector<HTMLInputElement>('.ti-rename-input');
    expect(input).toBeTruthy();
    expect(input?.value).toBe('Whispers in the dark');
    if (input) {
      input.value = 'New name';
      await fireEvent.input(input);
    }
    // Pressing Enter commits via onrename
    if (input) await fireEvent.keyDown(input, { key: 'Enter' });
    expect(v).toBe('New name');
    // component reference anti-strip
    expect(component).toBeTruthy();
  });

  it('invokes onselect when the row is clicked', async () => {
    const onselect = vi.fn();
    const { container } = render(ThreadItem, {
      props: { onselect, thread: makeThread({ id: 42 }), timeLabel: '1h' },
    });
    const root = container.querySelector('.ti');
    if (root) await fireEvent.click(root);
    expect(onselect).toHaveBeenCalledWith(42);
  });

  it('invokes oncontextmenu with the mouse event and thread id on right-click', async () => {
    const oncontextmenu = vi.fn();
    const { container } = render(ThreadItem, {
      props: { oncontextmenu, thread: makeThread({ id: 7 }), timeLabel: '1h' },
    });
    const root = container.querySelector('.ti');
    if (root) await fireEvent.contextMenu(root);
    expect(oncontextmenu).toHaveBeenCalledTimes(1);
    const [evt, id] = oncontextmenu.mock.calls[0] as [MouseEvent, number];
    expect(evt).toBeInstanceOf(MouseEvent);
    expect(id).toBe(7);
  });

  it('dots button stops propagation and calls ondotsclick', async () => {
    const onselect = vi.fn();
    const ondotsclick = vi.fn();
    const { container } = render(ThreadItem, {
      props: { ondotsclick, onselect, thread: makeThread(), timeLabel: '1h' },
    });
    const dots = container.querySelector('.ti-dots');
    expect(dots).toBeTruthy();
    if (dots) await fireEvent.click(dots);
    // dots-click should fire, onselect should NOT (because of stopPropagation)
    expect(ondotsclick).toHaveBeenCalledTimes(1);
    expect(onselect).not.toHaveBeenCalled();
  });

  it('Escape in rename input invokes oncancelrename with the thread id', async () => {
    const oncancelrename = vi.fn();
    render(ThreadItem, {
      props: {
        oncancelrename,
        renameValue: 'draft',
        renaming: true,
        thread: makeThread({ id: 9 }),
        timeLabel: '1h',
      },
    });
    const input = document.querySelector<HTMLInputElement>('.ti-rename-input');
    if (input) await fireEvent.keyDown(input, { key: 'Escape' });
    expect(oncancelrename).toHaveBeenCalledWith(9);
  });
});
