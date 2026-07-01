// avatar.ts — deterministic generated avatars for bots/personas that
// haven't uploaded an avatar image. Pure client-side, no backend, no
// randomness: the same name always produces the same avatar.
//
// Algorithm:
//   1. hash(name) → 32-bit integer
//   2. Split into byte-segments → hue1, hue2, angle, faceIndex
//   3. hue1/hue2 cover the full 0..359 wheel, with a fixed offset
//      of +90..+150 between them so the gradient is always pleasantly
//      complementary (not muddy).
//   4. Saturation 38..52% and lightness 76..83% — true pastel range.
//      Every color stays soft and creamy, never neon or acidic.
//   5. Angle is one of [90, 135, 180] so the gradient is diagonal-ish
//      (horizontal/vertical gradients look "off" at small sizes).
//   6. faceIndex picks one of FACES (12 kaomoji-style SVG faces drawn
//      with outline strokes on top of the gradient).
//
// The output is intentionally minimal: just the gradient string (CSS
// value) and the face index. The face SVG itself lives in
// GeneratedAvatar.svelte as a lookup table — this keeps the hash
// function pure and testable in isolation.

/** A simple 32-bit FNV-1a hash. Stable across JS engines, fast, no deps. */
function fnv1a(str: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    // 32-bit FNV prime multiplication via shift+add (avoids overflow
    // shenanigans — JS bitwise ops are signed 32-bit).
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h >>> 0;
}

/** Strip whitespace + non-printable chars, lowercase. Empty → "?". */
function normalizeName(name: string): string {
  const cleaned = name
    .normalize('NFKD')
    .replace(/[^\p{L}\p{N}]/gu, '')
    .toLowerCase();
  return cleaned.length === 0 ? '?' : cleaned;
}

/** Number of face variants in GeneratedAvatar.svelte. Keep in sync. */
export const FACE_COUNT = 12;

/** Angle options. Diagonal-ish to look good at small sizes. */
const ANGLES = [90, 135, 180] as const;

export interface GeneratedAvatarSpec {
  /** angle of the linear gradient, in degrees. */
  angle: number;
  /** index into GeneratedAvatar.svelte's FACES table. */
  face: number;
  /** CSS `linear-gradient(...)` value, ready to use as background. */
  gradient: string;
  /** hue of the first gradient stop, in degrees (0..359). */
  hue1: number;
  /** hue of the second gradient stop, in degrees (0..359). */
  hue2: number;
}

/**
 * Compute the avatar spec for a name. Deterministic: same name →
 * same gradient + same face. Empty/whitespace names use "?".
 *
 * @example
 *   generateAvatar("Luna") → { gradient: "linear-gradient(135deg, hsl(...), hsl(...))", face: 3, ... }
 */
export function generateAvatar(name: string): GeneratedAvatarSpec {
  const h = fnv1a(normalizeName(name));

  // Hue 1: re-mapped 0..255 → 0..359 (full wheel).
  // Saturation 38..52% and lightness 76..86% — true pastel range.
  // (v2 used 70..85% / 58..65% which was "vivid", not pastel —
  // vision confirmed it was borderline acidic on bright hues.)
  // Pastels read as "soft / creamy" — every color stays readable
  // against the white face strokes but never feels loud.
  const hue1Base = h & 0xff; // 0..255
  const hue1 = Math.round((hue1Base / 255) * 359);
  const sat1 = 38 + ((h >> 4) & 0xf); // 38..53
  const light1 = 76 + ((h >> 12) & 0x7); // 76..83

  // Hue 2: complementary offset (+90..+150), based on the next byte.
  const hue2Offset = 90 + ((h >> 8) & 0x3f); // 90..153
  const hue2 = (hue1 + hue2Offset) % 360;
  const sat2 = 38 + ((h >> 20) & 0xf); // 38..53
  const light2 = 76 + ((h >> 28) & 0x7); // 76..83

  // Angle: 3 choices, deterministic from bit 16-17.
  const angle = ANGLES[(h >> 16) & 0x3] ?? 135;

  // Face: 0..11 (12 variants — modulo into FACES length inside the
  // component so we don't break if a new face is added without
  // changing the hash function).
  const face = (h >> 20) & 0xf;

  const gradient = `linear-gradient(${angle}deg, hsl(${hue1} ${sat1}% ${light1}%), hsl(${hue2} ${sat2}% ${light2}%))`;

  return { angle, face, gradient, hue1, hue2 };
}
