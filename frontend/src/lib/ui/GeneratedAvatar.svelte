<!-- GeneratedAvatar — deterministic placeholder for bots/personas
     that haven't uploaded an avatar. Combines an HSL-derived linear
     gradient (from generateAvatar()) with one of 12 cute kaomoji-style
     SVG faces outlined on top in white.

     The face is sized to ~55% of the avatar diameter so the gradient
     breathes around it. A subtle radial highlight in the top-left
     corner gives the gradient depth without competing with the face. -->

<script lang="ts">
  import { generateAvatar } from '../avatar';

  // 12 face variants. All share the same color (currentColor = soft
  // white with 0.95 opacity) so they read clearly on every gradient.
  // Stroke is thicker (2.2px) than v1 to look more "cartoon-cute" at
  // small sizes. Every face has optional cheeks (small filled circles)
  // and eye sparkles (small filled dots inside the eyes) for a
  // kawaii feel.
  //
  // Anatomy: all faces are drawn in a 24x24 viewBox centered at (12, 12)
  // — the (0,0) origin is the center of the face, so a path like
  // "M -3.5 4 Q 0 7 3.5 4" draws a smile from the left cheek to the
  // right cheek, curving down to the chin. The eye y-coordinate is
  // around -1.5 (above center) and the mouth y around +4 (below).
  const FACES = [
    // 0: happy (◕‿◕) — round open eyes, upturned smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <ellipse cx="-4" cy="-1.5" rx="1.6" ry="1.8" fill="currentColor" fill-opacity="0.15" />
       <ellipse cx="4" cy="-1.5" rx="1.6" ry="1.8" fill="currentColor" fill-opacity="0.15" />
       <circle cx="-4" cy="-1.5" r="1.4" fill="none" />
       <circle cx="4" cy="-1.5" r="1.4" fill="none" />
       <circle cx="-3.5" cy="-2" r="0.4" fill="currentColor" stroke="none" />
       <circle cx="4.5" cy="-2" r="0.4" fill="currentColor" stroke="none" />
       <path d="M -3.5 4 Q 0 7 3.5 4" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 1: cool (◉_◉) — wide eyes with sparkle, flat mouth, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <ellipse cx="-4" cy="-1" rx="2" ry="2.2" fill="currentColor" fill-opacity="0.15" />
       <ellipse cx="4" cy="-1" rx="2" ry="2.2" fill="currentColor" fill-opacity="0.15" />
       <circle cx="-4" cy="-1" r="1.8" fill="none" />
       <circle cx="4" cy="-1" r="1.8" fill="none" />
       <circle cx="-3.4" cy="-1.6" r="0.5" fill="currentColor" stroke="none" />
       <circle cx="4.6" cy="-1.6" r="0.5" fill="currentColor" stroke="none" />
       <line x1="-3.5" y1="5" x2="3.5" y2="5" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 2: sleepy (ᴗ‿ᴗ) — closed curved eyes, big smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -5.5 -1.5 Q -3 0.2 -0.5 -1.5" />
       <path d="M 0.5 -1.5 Q 3 0.2 5.5 -1.5" />
       <path d="M -4 4 Q 0 7.5 4 4" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 3: surprised (°o°) — small round eyes, open round mouth, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <circle cx="-4" cy="-2" r="1.6" fill="none" />
       <circle cx="4" cy="-2" r="1.6" fill="none" />
       <circle cx="-3.5" cy="-2.5" r="0.4" fill="currentColor" stroke="none" />
       <circle cx="4.5" cy="-2.5" r="0.4" fill="currentColor" stroke="none" />
       <ellipse cx="0" cy="5" rx="2" ry="2.5" fill="currentColor" fill-opacity="0.2" />
       <ellipse cx="0" cy="5" rx="2" ry="2.5" fill="none" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 4: smirky (•‿•) — tiny dot eyes, asymmetric smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <circle cx="-4" cy="-2" r="1.1" fill="currentColor" />
       <circle cx="4" cy="-2" r="1.1" fill="currentColor" />
       <path d="M -3 4 Q 1 6 3.5 3.5" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 5: wink (◕‿‿) — one open eye with sparkle, one curved, smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <ellipse cx="-4" cy="-1.5" rx="1.6" ry="1.8" fill="currentColor" fill-opacity="0.15" />
       <circle cx="-4" cy="-1.5" r="1.4" fill="none" />
       <circle cx="-3.5" cy="-2" r="0.4" fill="currentColor" stroke="none" />
       <path d="M 2 -1.5 Q 4 0.2 6 -1.5" />
       <path d="M -3.5 4 Q 0 7 3.5 4" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 6: confused (◐_◑) — half-filled eyes, zigzag mouth, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -5.5 -1.5 A 1.5 1.5 0 0 1 -2.5 -1.5 L -2.5 0 L -5.5 0 Z" fill="currentColor" fill-opacity="0.6" />
       <path d="M 2.5 -1.5 A 1.5 1.5 0 0 1 5.5 -1.5 L 5.5 0 L 2.5 0 Z" fill="currentColor" fill-opacity="0.6" />
       <path d="M -3 5 Q -1.5 4 0 5 T 3 5" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 7: content (˘‿˘) — tilde eyes, small smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -5.5 -1.5 Q -3.5 -2.8 -1.5 -1.5" />
       <path d="M 1.5 -1.5 Q 3.5 -2.8 5.5 -1.5" />
       <path d="M -2.5 4.5 Q 0 6 2.5 4.5" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.35" stroke="none" />
     </g>`,
    // 8: in love (♥‿♥) — heart eyes, soft smile, BIG cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -5 -2.5 C -6 -4 -3.5 -4 -4 -2 C -4.5 -4 -2 -4 -3 -2.5 C -3.5 -1.5 -4 -1 -4 -1 C -4 -1 -4.5 -1.5 -5 -2.5 Z" fill="currentColor" stroke="none" transform="translate(0 0.5)" />
       <path d="M 3 -2.5 C 2 -4 4.5 -4 4 -2 C 3.5 -4 6 -4 5 -2.5 C 4.5 -1.5 4 -1 4 -1 C 4 -1 3.5 -1.5 3 -2.5 Z" fill="currentColor" stroke="none" transform="translate(0 0.5)" />
       <path d="M -2.5 5 Q 0 6 2.5 5" />
       <ellipse cx="-6.5" cy="3.5" rx="1.3" ry="0.8" fill="currentColor" fill-opacity="0.45" stroke="none" />
       <ellipse cx="6.5" cy="3.5" rx="1.3" ry="0.8" fill="currentColor" fill-opacity="0.45" stroke="none" />
     </g>`,
    // 9: crying happy (T_T) — teardrops below eyes, smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <line x1="-5" y1="-2.5" x2="-3" y2="-2.5" />
       <line x1="5" y1="-2.5" x2="3" y2="-2.5" />
       <line x1="-4.8" y1="-1" x2="-3.2" y2="-1" />
       <line x1="4.8" y1="-1" x2="3.2" y2="-1" />
       <path d="M -4 2 L -4.5 3.5 Q -4.8 4.5 -4 4.5 Q -3.2 4.5 -3.5 3.5 Z" fill="currentColor" stroke="none" />
       <path d="M 4 2 L 4.5 3.5 Q 4.8 4.5 4 4.5 Q 3.2 4.5 3.5 3.5 Z" fill="currentColor" stroke="none" />
       <path d="M -3 5.5 Q 0 7 3 5.5" />
       <ellipse cx="-6.5" cy="3.5" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
       <ellipse cx="6.5" cy="3.5" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
     </g>`,
    // 10: cat-like (=^.^=) — pointy ears via small triangles, slit eyes, smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -5.5 -3 L -4.5 -1 L -3.5 -3 Z" fill="currentColor" fill-opacity="0.7" />
       <path d="M 5.5 -3 L 4.5 -1 L 3.5 -3 Z" fill="currentColor" fill-opacity="0.7" />
       <ellipse cx="-4" cy="-1" rx="1.2" ry="0.6" fill="currentColor" />
       <ellipse cx="4" cy="-1" rx="1.2" ry="0.6" fill="currentColor" />
       <path d="M -3 4 Q 0 6.5 3 4" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
     </g>`,
    // 11: starry-eyed (✦‿✦) — star eyes (4-point star), soft smile, cheeks
    `<g stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" transform="translate(12 12)">
       <path d="M -4 -3 L -3.5 -1.5 L -2 -1 L -3.5 -0.5 L -4 1 L -4.5 -0.5 L -6 -1 L -4.5 -1.5 Z" fill="currentColor" stroke="none" />
       <path d="M 4 -3 L 4.5 -1.5 L 6 -1 L 4.5 -0.5 L 4 1 L 3.5 -0.5 L 2 -1 L 3.5 -1.5 Z" fill="currentColor" stroke="none" />
       <path d="M -3 4.5 Q 0 6.5 3 4.5" />
       <ellipse cx="-6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
       <ellipse cx="6.5" cy="3" rx="1.2" ry="0.7" fill="currentColor" fill-opacity="0.4" stroke="none" />
     </g>`,
  ];

  const {
    alt = '',
    block = false,
    name = '',
    shape = 'circle',
    size = 40,
  }: {
    /** Accessible alt text (defaults to "Avatar for {name}"). */
    alt?: string;
    /** Fill the parent container (width/height 100%, display block) — used by BotCard hero. */
    block?: boolean;
    /** The name to hash (bot name, persona name, etc.). */
    name?: string;
    /** circle = fully rounded (default for small avatars); rounded = 22% radius (square-ish, good for cards). */
    shape?: 'circle' | 'rounded' | 'square';
    /** Diameter in pixels. Ignored when block=true (100% of parent). */
    size?: number;
  } = $props();

  const spec = $derived(generateAvatar(name || '?'));
  const faceSvg = $derived(FACES[spec.face % FACES.length]);
  const borderRadius = $derived(shape === 'circle' ? '50%' : shape === 'rounded' ? '22%' : '6px');
  const accessibleName = $derived(name?.trim() ? name : '?');
</script>

<div
  class="ga"
  class:ga-block={block}
  role="img"
  aria-label={alt || `Avatar for ${accessibleName}`}
  style:width={block ? '100%' : `${size}px`}
  style:height={block ? '100%' : `${size}px`}
  style:background={spec.gradient}
  style:border-radius={borderRadius}
>
  <!-- Subtle radial highlight in the top-left for depth -->
  <div class="ga-highlight" aria-hidden="true"></div>
  <!-- The face: SVG with white strokes, sized relative to the avatar. -->
  <svg
    class="ga-face"
    viewBox="0 0 24 24"
    width={block ? '120' : Math.round(size * 0.6)}
    height={block ? '120' : Math.round(size * 0.6)}
    aria-hidden="true"
  >
    {@html faceSvg}
  </svg>
</div>

<style>
  .ga {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    overflow: hidden;
    user-select: none;
  }
  .ga-block {
    display: flex;
  }
  .ga-highlight {
    position: absolute;
    inset: 0;
    background: radial-gradient(
      circle at 25% 20%,
      rgba(255, 255, 255, 0.16) 0%,
      rgba(255, 255, 255, 0) 55%
    );
    pointer-events: none;
  }
  .ga-face {
    position: relative;
    z-index: 1;
    color: rgba(255, 255, 255, 0.94);
    /* Drop-shadow gives the face a soft "lifted" look against the
       gradient. v3 (pastel palette) needs a slightly stronger shadow
       to keep the white strokes readable on light backgrounds. */
    filter: drop-shadow(0 1.5px 2.5px rgba(0, 0, 0, 0.22));
  }
</style>
