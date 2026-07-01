// avatar.test.ts — vitest cases for the pure avatar generator.
// No DOM, no Svelte. Just FNV-1a + HSL math.

import { describe, expect, it } from 'vitest';

import { FACE_COUNT, generateAvatar } from '../avatar';

describe('generateAvatar', () => {
  it('returns a gradient string with linear-gradient and two hsl() stops', () => {
    const spec = generateAvatar('Luna');
    expect(spec.gradient).toMatch(/^linear-gradient\(\d+deg, hsl\(/);
    // Two hsl() stops
    expect((spec.gradient.match(/hsl\(/g) ?? []).length).toBe(2);
  });

  it('hues cover the full 0..359 range (any hue is possible)', () => {
    // Run a sample of names; the hues should fall across the wheel,
    // not all clustered in a small range.
    const hues = ['Aria', 'Luna', 'Hermes', 'Sage', 'Kai', 'Mira', 'Onyx'].map(
      (n) => generateAvatar(n).hue1,
    );
    for (const hue of hues) {
      expect(hue).toBeGreaterThanOrEqual(0);
      expect(hue).toBeLessThan(360);
    }
    // Sanity: at least one hue is < 180 and at least one is >= 180
    // (not all clustered in one half). With 7 random names, this
    // should hold with probability ~1.
    expect(hues.some((h) => h < 180)).toBe(true);
    expect(hues.some((h) => h >= 180)).toBe(true);
  });

  it('face is in 0..15 (16-slot hash, modded into FACE_COUNT in the component)', () => {
    for (const name of ['Aria', 'Luna', 'Hermes', 'Sage', 'Kai', 'Mira', 'Onyx']) {
      const { face } = generateAvatar(name);
      expect(face).toBeGreaterThanOrEqual(0);
      expect(face).toBeLessThanOrEqual(15);
    }
  });

  it('exposes FACE_COUNT = 12 (must match the FACES array in GeneratedAvatar.svelte)', () => {
    expect(FACE_COUNT).toBe(12);
  });

  it('angle is one of 90, 135, 180', () => {
    for (const name of ['Aria', 'Luna', 'Hermes', 'Sage', 'Kai', 'Mira', 'Onyx']) {
      const { angle } = generateAvatar(name);
      expect([90, 135, 180]).toContain(angle);
    }
  });

  it('is deterministic — same name → same output', () => {
    const a = generateAvatar('Aria');
    const b = generateAvatar('Aria');
    expect(a).toEqual(b);
  });

  it('different names usually produce different outputs', () => {
    const a = generateAvatar('Aria');
    const b = generateAvatar('Luna');
    // At least one field should differ (gradient, hue1, hue2, or face)
    const same =
      a.gradient === b.gradient &&
      a.hue1 === b.hue1 &&
      a.hue2 === b.hue2 &&
      a.angle === b.angle &&
      a.face === b.face;
    expect(same).toBe(false);
  });

  it('normalizes case and whitespace — "Luna" and "  luna  " give the same result', () => {
    const a = generateAvatar('Luna');
    const b = generateAvatar('  luna  ');
    expect(a).toEqual(b);
  });

  it('strips special characters — "Mr. Luna!" gives same result as "Mr Luna"', () => {
    const a = generateAvatar('Mr. Luna!');
    const b = generateAvatar('Mr Luna');
    expect(a).toEqual(b);
  });

  it('handles emoji names by stripping them to "?"', () => {
    const a = generateAvatar('🌙');
    const b = generateAvatar('?');
    expect(a).toEqual(b);
  });

  it('handles empty string as "?"', () => {
    const a = generateAvatar('');
    const b = generateAvatar('?');
    expect(a).toEqual(b);
  });

  it('produces a 360-degree-distinct hue2 relative to hue1 (always offset 90..153°)', () => {
    // hue2 = (hue1 + 90..150) % 360, so the offset is always > 0
    for (const name of ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']) {
      const { hue1, hue2 } = generateAvatar(name);
      const offset = (hue2 - hue1 + 360) % 360;
      expect(offset).toBeGreaterThanOrEqual(90);
      expect(offset).toBeLessThanOrEqual(153);
    }
  });

  it('saturation is in 38..53% range (true pastel — soft, never neon)', () => {
    // hsl() format is "hsl(H S% L%)" — the first % is saturation.
    // Lightness varies 76..83% for variety; only saturation is locked.
    for (const name of ['Aria', 'Luna', 'Hermes', 'Sage', 'Kai']) {
      const { gradient } = generateAvatar(name);
      // Match "N%"; in "H S% L%, H S% L%" the sats are at indices 0 and 2,
      // the lightnesses are at indices 1 and 3.
      const satMatches = gradient.match(/\d+(?=%)/g) ?? [];
      const sat1 = parseInt(satMatches[0] ?? '0', 10);
      const sat2 = parseInt(satMatches[2] ?? '0', 10);
      expect(sat1).toBeGreaterThanOrEqual(38);
      expect(sat1).toBeLessThanOrEqual(53);
      expect(sat2).toBeGreaterThanOrEqual(38);
      expect(sat2).toBeLessThanOrEqual(53);
    }
  });

  it('lightness is in 76..83% range (soft pastel — never muddy or dark)', () => {
    // The 2nd and 4th "%" numbers in the gradient are the lightness values.
    for (const name of ['Aria', 'Luna', 'Hermes', 'Sage', 'Kai']) {
      const { gradient } = generateAvatar(name);
      const pcts = gradient.match(/\d+(?=%)/g) ?? [];
      const light1 = parseInt(pcts[1] ?? '0', 10);
      const light2 = parseInt(pcts[3] ?? '0', 10);
      expect(light1).toBeGreaterThanOrEqual(76);
      expect(light1).toBeLessThanOrEqual(83);
      expect(light2).toBeGreaterThanOrEqual(76);
      expect(light2).toBeLessThanOrEqual(83);
    }
  });
});
