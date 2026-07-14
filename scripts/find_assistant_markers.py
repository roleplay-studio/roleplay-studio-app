#!/usr/bin/env python3
"""Discover TODO(for-assistant) markers across the repo.

Workflow documented in AGENTS.md §9. Quick reference::

    uv run python scripts/find_assistant_markers.py               # full repo
    uv run python scripts/find_assistant_markers.py api/routes     # one path

For each marker we print ``path:line | text`` so the assistant can
decide what to change without re-reading the file from scratch.
Output is grouped by file and sorted by line number so a single
edit at the bottom of the suggestion list maps cleanly to one
patch call.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = re.compile(r"(TODO\(for-assistant\):|FIXME\(hermes\):|REVIEW:)")
EXTENSIONS = {".py", ".ts", ".tsx", ".svelte", ".js", ".toml", ".md", ".html"}

# Paths whose contents describe, but don't trigger, the marker
# pattern. The AGENTS.md section §9 is the canonical "what does a
# marker look like" reference — filtering it out keeps the helper
# silent on documentation. ``node_modules`` is third-party.
EXCLUDE_PATH_PARTS = ("node_modules", ".venv", ".git", "playwright-report")


def _iter_lines(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                yield lineno, raw.rstrip("\n")
    except (UnicodeDecodeError, OSError):
        # Binary file or unreadable — skip silently.
        return


def _scan(target: Path) -> list[tuple[Path, int, str]]:
    """Return [(path, lineno, marker_text), ...] for every marker
    in ``target`` (file or directory tree).
    """
    if target.is_file():
        files = [target]
    else:
        files = sorted(
            p for p in target.rglob("*")
            if p.is_file()
            and p.suffix in EXTENSIONS
            and not any(part in EXCLUDE_PATH_PARTS for part in p.parts)
        )
    out: list[tuple[Path, int, str]] = []
    for path in files:
        # Skip AGENTS.md — its §9 section is the documentation
        # describing marker syntax, not a real annotation.
        rel = path.relative_to(ROOT)
        if rel.name in {"AGENTS.md", "AGENTS.ru.md"}:
            continue
        # The script itself includes the marker regex; skip.
        if path.suffix == ".py" and "find_assistant_markers" in path.name:
            continue
        for lineno, raw in _iter_lines(path):
            m = MARKER.search(raw)
            if m:
                # Strip the leading comment marker for compact display.
                marker_text = m.group(1) + raw[m.end():].strip()
                out.append((rel, lineno, marker_text))
    return out


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        target = Path(argv[1]).resolve()
    else:
        target = ROOT
    hits = _scan(target)
    if not hits:
        print("No TODO(for-assistant) markers found.", file=sys.stderr)
        return 0

    # Group by file so a single read_file call covers them.
    by_file: dict[Path, list[tuple[int, str]]] = {}
    for path, lineno, text in hits:
        by_file.setdefault(path, []).append((lineno, text))

    for path in sorted(by_file.keys()):
        sep = "=" * 60
        print()
        print(f"{sep}")
        print(f"== {path} ({len(by_file[path])} marker(s))")
        print(f"{sep}")
        for lineno, text in sorted(by_file[path]):
            print(f"  L{lineno}  | {text}")
    print(f"\nTotal: {len(hits)} marker(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
