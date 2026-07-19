import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import type { BotType } from '../api';
import type { BotSortDir, BotSortKey } from '../botsBrowse';

import BotsToolbar from '../BotsToolbar.svelte';

/**
 * Component test for ``BotsToolbar`` (introduced by
 * ``improve-bot-editor``). The toolbar is a controlled component — it
 * owns no state itself, only renders the three controls and forwards
 * user input to its callbacks. The parent (``BotsPage``) feeds the
 * callbacks back through ``$state`` and the ``botsBrowse`` helpers.
 *
 * We intentionally do NOT mock ``../api`` here. ``BotsToolbar`` reads
 * the static ``BOT_TYPES`` catalogue directly; the catalogue has been
 * stable across the project's history (de/ru 3-type enum) and the test
 * asserts the *behaviour* of the chip group against that catalogue, so
 * pinning to the real data is more honest than mocking it.
 */
function makeProps(over: Partial<{
  activeTypes: BotType[];
  onqueryChange: (q: string) => void;
  onsortChange: (k: BotSortKey, d: BotSortDir) => void;
  ontypesChange: (t: BotType[]) => void;
  query: string;
  sortDir: BotSortDir;
  sortKey: BotSortKey;
}> = {}) {
  return {
    activeTypes: over.activeTypes ?? [],
    onqueryChange: over.onqueryChange ?? vi.fn(),
    onsortChange: over.onsortChange ?? vi.fn(),
    ontypesChange: over.ontypesChange ?? vi.fn(),
    query: over.query ?? '',
    sortDir: over.sortDir ?? ('desc' as BotSortDir),
    sortKey: over.sortKey ?? ('id' as BotSortKey),
  };
}

describe('BotsToolbar', () => {
  it('renders the three sections (sort, filter, search)', () => {
    const { container } = render(BotsToolbar, { props: makeProps() });
    // Sort label
    expect(container.textContent).toContain('Sort by');
    // Filter label
    expect(container.textContent).toContain('Filter by type');
    // Search placeholder
    const search = container.querySelector('input[placeholder*="Search"]');
    expect(search).toBeTruthy();
  });

  it('renders one chip per BotType from BOT_TYPES catalogue', () => {
    const { container } = render(BotsToolbar, { props: makeProps() });
    // BOT_TYPES catalogue has 3 entries: rp, assistant, agent.
    // We assert on labels to avoid coupling to i18n keys.
    expect(container.textContent).toContain('RolePlay');
    expect(container.textContent).toContain('Assistant');
    // Agent label is "Agent" but we just check the chip container is
    // populated — the exact wording depends on i18n.ts.
    const chipButtons = container.querySelectorAll('button.bots-toolbar-chip');
    // 3 type chips + the "Clear all" button is hidden when no chips
    // are active (we'll assert that separately).
    expect(chipButtons.length).toBeGreaterThanOrEqual(3);
  });

  it('shows the "Clear all" affordance only when at least one type is active', () => {
    const { container: empty } = render(BotsToolbar, {
      props: makeProps({ activeTypes: [] }),
    });
    expect(empty.textContent).not.toContain('Clear all');

    const { container: withOne } = render(BotsToolbar, {
      props: makeProps({ activeTypes: ['rp'] }),
    });
    expect(withOne.textContent).toContain('Clear all');
  });

  it('marks active chips with an aria-pressed=true attribute', () => {
    const { container } = render(BotsToolbar, {
      props: makeProps({ activeTypes: ['rp', 'assistant'] }),
    });
    const rpChip = Array.from(container.querySelectorAll('button.bots-toolbar-chip')).find(
      (b) => b.textContent?.includes('RolePlay'),
    );
    const assistantChip = Array.from(container.querySelectorAll('button.bots-toolbar-chip')).find(
      (b) => b.textContent?.includes('Assistant'),
    );
    expect(rpChip?.getAttribute('aria-pressed')).toBe('true');
    expect(assistantChip?.getAttribute('aria-pressed')).toBe('true');
  });

  it('clicking a chip toggles it through ontypesChange (single-select off → on)', async () => {
    const ontypesChange = vi.fn();
    const { container } = render(BotsToolbar, {
      props: makeProps({ activeTypes: [], ontypesChange }),
    });
    const rpChip = Array.from(container.querySelectorAll('button.bots-toolbar-chip')).find(
      (b) => b.textContent?.includes('RolePlay'),
    ) as HTMLButtonElement;
    await fireEvent.click(rpChip);
    expect(ontypesChange).toHaveBeenCalledWith(['rp']);
  });

  it('clicking an active chip removes it from the selection', async () => {
    const ontypesChange = vi.fn();
    const { container } = render(BotsToolbar, {
      props: makeProps({ activeTypes: ['rp', 'assistant'], ontypesChange }),
    });
    const rpChip = Array.from(container.querySelectorAll('button.bots-toolbar-chip')).find(
      (b) => b.textContent?.includes('RolePlay'),
    ) as HTMLButtonElement;
    await fireEvent.click(rpChip);
    // Click on an already-active chip removes it; the other active
    // type ("assistant") survives. Order matters — the toolbar
    // preserves the catalogue order from BOT_TYPES, so assistant
    // comes after rp.
    expect(ontypesChange).toHaveBeenCalledWith(['assistant']);
  });

  it('"Clear all" empties the active types', async () => {
    const ontypesChange = vi.fn();
    const { container } = render(BotsToolbar, {
      props: makeProps({ activeTypes: ['rp', 'assistant', 'agent'], ontypesChange }),
    });
    const clearBtn = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Clear all'),
    ) as HTMLButtonElement;
    await fireEvent.click(clearBtn);
    expect(ontypesChange).toHaveBeenCalledWith([]);
  });

  it('typing in the search input forwards the value via onqueryChange', async () => {
    const onqueryChange = vi.fn();
    const { container } = render(BotsToolbar, {
      props: makeProps({ onqueryChange }),
    });
    const input = container.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'lor' } });
    expect(onqueryChange).toHaveBeenCalledWith('lor');
  });

  it('reflects the current query prop back into the input value', () => {
    const { container } = render(BotsToolbar, {
      props: makeProps({ query: 'pre-filled' }),
    });
    const input = container.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
    expect(input.value).toBe('pre-filled');
  });

  it('emits the correct sort dimension+direction through onsortChange', async () => {
    const onsortChange = vi.fn();
    // The toolbar wraps the project's ``<Select>`` component, which is a
    // Raycast-style custom dropdown (a ``<button class="ray-select-trigger">``
    // opens a popover of options, not a native ``<select>``). We drive it
    // by clicking the trigger to open the menu, then clicking the option
    // whose label matches "Name (A→Z)" / "Most chats first" / etc.
    const { container, getByText } = render(BotsToolbar, {
      props: makeProps({ onsortChange }),
    });
    const trigger = container.querySelector('button.ray-select-trigger') as HTMLButtonElement;
    expect(trigger).toBeTruthy();
    await fireEvent.click(trigger);
    // After open, the option for "name asc" becomes visible in the
    // popover — Select renders options as buttons too.
    const nameAscOption = getByText('Name (A→Z) ↑');
    await fireEvent.click(nameAscOption);
    expect(onsortChange).toHaveBeenCalledWith('name', 'asc');
  });

  it('reflects the current sort dimension+direction on the trigger button', () => {
    const { container } = render(BotsToolbar, {
      props: makeProps({ sortKey: 'thread_count', sortDir: 'desc' }),
    });
    // The trigger button shows the selected option's label.
    // Includes the "↓" arrow suffix added in the i18n fix to make
    // the sort direction unambiguous at a glance (see design.md
    // open-question Q1 follow-up and the botsLibraryI18n test
    // pinning these exact strings).
    const trigger = container.querySelector('button.ray-select-trigger') as HTMLButtonElement;
    expect(trigger.textContent).toContain('Most chats first ↓');
  });

  it('renders every chip as a button with ≥44px minimum tap area class', () => {
    // The mobile touch-target contract (DESIGN.md §Do's and Don'ts,
    // MOBILE_PLAN.md Phase 4.5) requires tap area ≥ 44×44px. The
    // toolbar pins this via a utility class — we assert presence,
    // not the rendered pixel size (jsdom doesn't measure layout).
    const { container } = render(BotsToolbar, {
      props: makeProps({ activeTypes: ['rp'] }),
    });
    const chips = container.querySelectorAll('button.bots-toolbar-chip');
    for (const chip of chips) {
      expect(chip.className).toContain('min-h-11');
    }
  });
});