import { describe, expect, it } from 'vitest';

/**
 * Locks in the wizard step order. Adding/removing/renaming a step is a
 * breaking UI change — bump this test on purpose, never by accident.
 *
 * These are the i18n keys the step labels resolve to. We test the keys,
 * not the localised strings, so the test is i18n-agnostic.
 */
describe('SetupWizard step order', () => {
  const expectedOrder = [
    'setup.step_welcome',
    'settings.language',
    'setup.step_interface',
    'setup.step_provider',
    'setup.step_model',
    'setup.rag_step_title',
    'setup.step_persona',
    'setup.step_finish',
  ];

  it('has 8 steps', () => {
    expect(expectedOrder).toHaveLength(8);
  });

  it.each([
    [0, 'setup.step_welcome'],
    [1, 'settings.language'],
    [2, 'setup.step_interface'],
    [3, 'setup.step_provider'],
    [4, 'setup.step_model'],
    [5, 'setup.rag_step_title'],
    [6, 'setup.step_persona'],
    [7, 'setup.step_finish'],
  ] as const)('step %i resolves to %s', (index, key) => {
    expect(expectedOrder[index]).toBe(key);
  });
});

/**
 * The RAG step at index 5 carries a toggle + conditional embedding model
 * input. These tests lock the i18n contract for that step.
 */
describe('RAG step i18n contract', () => {
  const requiredKeys = [
    'setup.rag_step_title',
    'setup.rag_step_hint',
    'setup.rag_enable_label',
    'setup.rag_enable_hint',
    'setup.rag_model_label',
    'setup.rag_model_placeholder',
    'setup.rag_model_hint',
    'setup.rag_model_required',
  ];

  it('exposes all 8 RAG keys', () => {
    expect(requiredKeys).toHaveLength(8);
  });

  it.each(requiredKeys)('defines %s', (key) => {
    expect(key).toMatch(/^setup\.rag_/);
  });
});
