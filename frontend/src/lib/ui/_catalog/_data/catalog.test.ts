// _data/catalog.test.ts — vitest snapshot test for the static catalog
// registry. Verifies invariants that should hold across all entries,
// not their exact values, so adding new entries won't fail on
// divergence — the snapshot file is committed and inspected manually.

import { describe, expect, it } from 'vitest';

import { CATALOG } from './catalog';

describe('CATALOG', () => {
  it('has at least 30 entries (foundations + atomic + composite)', () => {
    expect(CATALOG.length).toBeGreaterThanOrEqual(30);
  });

  it('all slugs are unique', () => {
    const slugs = CATALOG.map((e) => e.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it('all titles are unique', () => {
    const titles = CATALOG.map((e) => e.title);
    expect(new Set(titles).size).toBe(titles.length);
  });

  it('all groups are valid (foundations/atomic/composite)', () => {
    const valid = new Set(['atomic', 'composite', 'foundations']);
    for (const e of CATALOG) {
      expect(valid.has(e.group), `Invalid group: ${e.group} for ${e.slug}`).toBe(true);
    }
  });

  it('all entries have a non-empty description', () => {
    for (const e of CATALOG) {
      expect(e.description.length, `Empty description for ${e.slug}`).toBeGreaterThan(10);
    }
  });

  it('non-foundations entries have at least one snippet', () => {
    for (const e of CATALOG) {
      if (e.group !== 'foundations') {
        expect(e.snippets.length, `No snippets for ${e.slug} (${e.group})`).toBeGreaterThan(0);
      }
    }
  });

  it('all entries have a valid source path under frontend/src/', () => {
    for (const e of CATALOG) {
      expect(e.source, `Bad source for ${e.slug}`).toMatch(/^frontend\/src\//);
    }
  });

  it('foundations entries do not declare props (they are static)', () => {
    for (const e of CATALOG) {
      if (e.group === 'foundations') {
        expect(e.props, `Foundations ${e.slug} should not have props`).toBeUndefined();
      }
    }
  });

  it('non-foundations entries declare at least one prop (GlobalDropZone is the only allowed exception)', () => {
    for (const e of CATALOG) {
      if (e.group !== 'foundations' && e.slug !== 'global-drop-zone') {
        expect(
          e.props?.length,
          `${e.slug} (${e.group}) should have at least 1 prop`,
        ).toBeGreaterThan(0);
      }
    }
  });

  it('all snippet langs are valid (svelte/ts/bash)', () => {
    const valid = new Set(['bash', 'svelte', 'ts']);
    for (const e of CATALOG) {
      for (const s of e.snippets) {
        expect(valid.has(s.lang), `Bad lang ${s.lang} in ${e.slug}`).toBe(true);
      }
    }
  });

  it('all entries have a working demo loader (returns a Promise that resolves to a component)', async () => {
    // Swallow per-entry errors so a single broken demo doesn't fail the
    // whole test — we just want to know the loader returned a thenable.
    const checks = CATALOG.map((e) =>
      e
        .demo()
        .then((mod) => ({ ok: !!mod?.default, slug: e.slug }))
        .catch(() => ({ ok: false, slug: e.slug })),
    );
    const results = await Promise.all(checks);
    for (const r of results) {
      expect(r.ok, `demo() failed for ${r.slug}`).toBe(true);
    }
  });
});
