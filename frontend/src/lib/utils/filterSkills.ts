/**
 * Pure filter for the Skills library. See spec §6.6.
 *
 * Mirrors backend semantics (api.listSkills(q=..., tag=...)):
 * - `q` is a case-insensitive substring match against name and
 *   description.
 * - `tags`: empty → all; non-empty → skill must have at least
 *   one tag in the selected set (OR semantics).
 *
 * Exported as a utility so unit tests can import it directly
 * without mounting the page component (heavy UI deps).
 */
import type { SkillDTO } from '../api';

export function filterSkills(
  skills: SkillDTO[],
  q: string,
  tags: string[]
): SkillDTO[] {
  const needle = q.trim().toLowerCase();
  return skills.filter((s) => {
    if (
      needle &&
      !s.name.toLowerCase().includes(needle) &&
      !s.description.toLowerCase().includes(needle)
    ) {
      return false;
    }
    if (tags.length === 0) return true;
    const skillTagSet = new Set(s.tags.map((t) => t.toLowerCase()));
    return tags.some((t) => skillTagSet.has(t.toLowerCase()));
  });
}