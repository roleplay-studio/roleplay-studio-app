/**
 * SkillPicker — vitest unit tests.
 *
 * Pure presentation logic, no fetch calls — we feed all skills
 * and attachedIds via props, then assert onchange semantics.
 */
import { describe, expect, it, vi } from 'vitest';

import { render } from '@testing-library/svelte';

import type { SkillDTO } from '../api';

import SkillPicker from '../SkillPicker.svelte';

const SARC = (id = 1): SkillDTO => ({
  created_at: '2026-07-17T00:00:00Z',
  description: 'dry wit',
  id,
  instruction: 'apply when user opens with sarcasm',
  name: 'Sarcastic',
  tags: ['tone'],
  updated_at: '2026-07-17T00:00:00Z',
});
const CONCISE = (id = 2): SkillDTO => ({
  created_at: '2026-07-17T00:00:00Z',
  description: 'short replies',
  id,
  instruction: 'cap at 3 sentences',
  name: 'Concise',
  tags: ['tone'],
  updated_at: '2026-07-17T00:00:00Z',
});

describe('SkillPicker', () => {
  it('renders one pill per available skill', () => {
    const { getAllByRole } = render(SkillPicker, {
      props: { allSkills: [SARC(), CONCISE()], attachedIds: [] },
    });
    const buttons = getAllByRole('button');
    expect(buttons).toHaveLength(2);
  });

  it('marks attached skills with .selected class', () => {
    const { container } = render(SkillPicker, {
      props: { allSkills: [SARC(), CONCISE()], attachedIds: [1] },
    });
    const pills = container.querySelectorAll('.sp-pill');
    expect(pills[0]?.className).toContain('selected');
    expect(pills[1]?.className).not.toContain('selected');
  });

  it('calls onchange with appended id when an unselected pill is clicked', async () => {
    const onchange = vi.fn();
    const { container } = render(SkillPicker, {
      props: { allSkills: [SARC(), CONCISE()], attachedIds: [], onchange },
    });
    const firstPill = container.querySelectorAll('.sp-pill')[0] as HTMLButtonElement;
    await firstPill.click();
    expect(onchange).toHaveBeenCalledWith([1]);
  });

  it('calls onchange with the id removed when a selected pill is clicked', async () => {
    const onchange = vi.fn();
    const { container } = render(SkillPicker, {
      props: { allSkills: [SARC(), CONCISE()], attachedIds: [1, 2], onchange },
    });
    const firstPill = container.querySelectorAll('.sp-pill')[0] as HTMLButtonElement;
    await firstPill.click();
    expect(onchange).toHaveBeenCalledWith([2]);
  });

  it('does NOT add a new skill when maxReached is true', async () => {
    const onchange = vi.fn();
    const { container } = render(SkillPicker, {
      props: {
        allSkills: [SARC(), CONCISE()],
        attachedIds: [1],
        maxReached: true,
        onchange,
      },
    });
    const secondPill = container.querySelectorAll('.sp-pill')[1] as HTMLButtonElement;
    await secondPill.click();
    expect(onchange).not.toHaveBeenCalled();
  });

  it('disables unselected pills when maxReached is true', () => {
    const { container } = render(SkillPicker, {
      props: {
        allSkills: [SARC(), CONCISE()],
        attachedIds: [1],
        maxReached: true,
      },
    });
    const pills = container.querySelectorAll('.sp-pill') as NodeListOf<HTMLButtonElement>;
    // First is selected → not disabled; second is unselected → disabled.
    expect(pills[0].disabled).toBe(false);
    expect(pills[1].disabled).toBe(true);
  });

  it('still allows removing an attached skill even when maxReached is true', async () => {
    const onchange = vi.fn();
    const { container } = render(SkillPicker, {
      props: {
        allSkills: [SARC(), CONCISE()],
        attachedIds: [1],
        maxReached: true,
        onchange,
      },
    });
    const firstPill = container.querySelectorAll('.sp-pill')[0] as HTMLButtonElement;
    await firstPill.click();
    expect(onchange).toHaveBeenCalledWith([]);
  });

  it('renders the empty-state hint when no skills exist', () => {
    const { getByText } = render(SkillPicker, {
      props: { allSkills: [], attachedIds: [] },
    });
    expect(getByText(/No skills yet/i)).toBeTruthy();
  });

  it('renders the maxReached hint when at limit', () => {
    const { container } = render(SkillPicker, {
      props: {
        allSkills: [SARC(), CONCISE()],
        attachedIds: [1],
        maxReached: true,
      },
    });
    expect(container.querySelector('.sp-hint')?.textContent).toMatch(/Max reached/i);
  });
});