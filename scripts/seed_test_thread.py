#!/usr/bin/env python3
"""
Seed a synthetic chat thread with N messages directly into the SQLite
database, bypassing the LLM. Useful for performance testing the chat UI
without spending API tokens or waiting for streaming responses.

The messages cycle through 5 length profiles (short, medium-short,
medium, very-short, long) so the rendered bubble heights vary enough
to stress-test the scroll-anchor algorithm. We deliberately alternate
between `user` and `assistant` roles so the flex layout is the same
as a real conversation.

Usage:
    # Default: 500 messages on bot 10 (Сомния) in thread 1000.
    .venv/bin/python scripts/seed_test_thread.py

    # Custom count, bot, thread id, name:
    .venv/bin/python scripts/seed_test_thread.py \\
        --count 1000 --bot 10 --thread 2000 --name "perf-1k"

    # Clean up a previously-seeded thread (deletes thread + cascades
    # to all its conversations):
    .venv/bin/python scripts/seed_test_thread.py --thread 1000 --cleanup

    # Use a different database path (default: <repo>/conversations.db):
    .venv/bin/python scripts/seed_test_thread.py --db /tmp/test.db

Why not use `psql` / direct `sqlite3`? Because the script is version-
controlled alongside the project, and Python's stdlib sqlite3 lets us
embed the test-data as readable Python and iterate without retyping
a long SQL heredoc. The SQL itself is plain INSERTs — no ORM magic
that would obscure what's actually being written.

The script is **idempotent** in two ways:
  * If the target thread already exists, we wipe its messages and
    re-seed (unless --keep-existing is set).
  * The chosen thread id range (1000+) is unlikely to collide with
    real threads; the script also refuses to operate on a thread
    whose name doesn't start with `seed_`, `stress_`, `perf_`, or
    `test_` unless --force is set, to protect against accidentally
    overwriting a real conversation.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_DB = "conversations.db"
DEFAULT_BOT = 10  # Сомния — has branching/versioning code paths, so it's
# a good representative of the worst case.
DEFAULT_THREAD = 1000
DEFAULT_NAME = "stress_scroll_500"
DEFAULT_COUNT = 500
DEFAULT_PERSONA = 1  # Дмитрий

# Thread names must start with one of these to be eligible for
# --cleanup / --reset, unless --force is set. Real conversations
# named like "DEBUG1" or "The Girl with My Eyes" are safe.
PROTECTED_PREFIXES = ("seed_", "stress_", "perf_", "test_")

# Five length profiles, cycled by `n % 5`. Index 0 = the "long"
# profile, which the d2e05185 commit's scroll-anchor test relied on
# heavily to expose the content-visibility bug (long messages have
# heights well above the 140px contain-intrinsic-size, so the
# "scrollHeight delta" approach undercounted badly).
PROFILES = [
    {
        "content": (
            "длинный текст: Сомния отвечает на игривый вызов пользователя, "
            "переключаясь между ролями диктора и Алисы, и заканчивает тем, "
            "что подкладывает подушку тебе под голову и шепчет что-то нежное "
            "на ухо, заставляя тебя краснеть и терять дар речи на несколько "  # noqa: RUF001
            "секунд, пока она не отстраняется с довольной усмешкой и не "  # noqa: RUF001
            "щёлкает пальцами, переключая сцену на школьный коридор, где "
            "мимо проходит Алиса в короткой юбке, бросая на тебя взгляд искоса."
        ),
        "short": "длинный ответ Сомнии (сжато)",
    },
    {"content": 'короткий ответ: "Да, я заметил."', "short": "короткий ответ"},
    {
        "content": (
            "средний текст. Сомния усмехается и переключает сцену — теперь "
            "ты стоишь в школьном коридоре, и мимо проходит та самая Алиса в "
            "короткой юбке, бросая на тебя взгляд искоса, от которого у тебя "  # noqa: RUF001
            "перехватывает дыхание и хочется сказать что-то умное, но в "
            "голове только белый шум."
        ),
        "short": "средний ответ (сжато)",
    },
    {"content": "совсем короткое: ок", "short": "ок"},
    {
        "content": (
            "средний текст: диалог развивается, Сомния подбрасывает новый "
            "поворот в сцене, и тебе приходится быстро импровизировать, чтобы "
            "не выпасть из роли — иначе Алиса заметит подвох и сюжет пойдёт "
            "по совсем другой ветке, где диктор вмешивается напрямую."
        ),
        "short": "средний ответ (сжато)",
    },
]


# ── Helpers ──────────────────────────────────────────────────────────────


def is_protected_name(name: str) -> bool:
    """True if the thread's name doesn't start with a recognised
    test-only prefix. Used to refuse destructive operations on
    real conversations."""
    return not name.startswith(PROTECTED_PREFIXES)


def get_thread_name(conn: sqlite3.Connection, thread_id: int) -> str | None:
    cur = conn.execute("SELECT name FROM chat_threads WHERE id = ?", (thread_id,))
    row = cur.fetchone()
    return row[0] if row else None


def cleanup_thread(conn: sqlite3.Connection, thread_id: int, force: bool) -> bool:
    """Delete the thread and cascade-delete its conversations.
    Returns True if a delete happened."""
    name = get_thread_name(conn, thread_id)
    if name is None:
        print(f"  thread {thread_id} not found, nothing to clean")
        return False
    if not force and is_protected_name(name):
        print(
            f"  refusing to clean thread {thread_id} (name={name!r}): "
            f"name doesn't start with one of {PROTECTED_PREFIXES}. "
            f"Pass --force to override.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  deleting thread {thread_id} (name={name!r})")
    conn.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM chat_threads WHERE id = ?", (thread_id,))
    return True


def create_thread(
    conn: sqlite3.Connection,
    thread_id: int,
    bot_id: int,
    name: str,
    persona_id: int,
) -> None:
    conn.execute(
        "INSERT INTO chat_threads (id, bot_id, name, summary, persona_id, created_at) "
        "VALUES (?, ?, ?, NULL, ?, ?)",
        (
            thread_id,
            bot_id,
            name,
            persona_id,
            datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC).isoformat(),
        ),
    )


def insert_messages(
    conn: sqlite3.Connection,
    thread_id: int,
    count: int,
    start_time: datetime,
) -> None:
    """Bulk-insert `count` alternating user/assistant messages with
    realistic timestamps and 5 cycling length profiles. The whole
    thing is one transaction so the thread is never half-seeded."""
    rows: list[tuple] = []
    for n in range(1, count + 1):
        profile = PROFILES[(n - 1) % len(PROFILES)]
        role = "user" if n % 2 == 1 else "assistant"
        ts = start_time + timedelta(seconds=n * 5)
        rows.append(
            (
                thread_id,
                role,
                f"Сообщение #{n} — {profile['content']}",
                profile["short"],
                ts.isoformat(),
            )
        )
    conn.executemany(
        "INSERT INTO conversations "
        "(thread_id, role, content, short_content, timestamp, "
        " branch_group, branch_index, is_active) "
        "VALUES (?, ?, ?, ?, ?, NULL, 0, 1)",
        rows,
    )


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a synthetic chat thread for UI / perf testing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB, help="Path to SQLite database (default: %(default)s)"
    )
    parser.add_argument(
        "--bot", type=int, default=DEFAULT_BOT, help="Bot id (default: %(default)s)"
    )
    parser.add_argument(
        "--thread",
        type=int,
        default=DEFAULT_THREAD,
        help="Thread id to create/replace (default: %(default)s). "
        "Use 1000+ to avoid collision with real threads.",
    )
    parser.add_argument("--name", default=DEFAULT_NAME, help="Thread name (default: %(default)s)")
    parser.add_argument(
        "--persona", type=int, default=DEFAULT_PERSONA, help="Persona id (default: %(default)s)"
    )
    parser.add_argument(
        "--count", type=int, default=DEFAULT_COUNT, help="Number of messages (default: %(default)s)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the thread (and all its messages) and exit. "
        "Refuses to operate on real conversations unless --force is set.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow destructive operations on threads whose name "
        "doesn't start with a recognised test prefix.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="If the thread already exists with messages, keep them and "
        "just re-create the (empty) thread row. Default is to wipe "
        "and re-seed.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"database not found: {db_path}", file=sys.stderr)
        print(
            "  (the default lives at <repo>/conversations.db; start the backend once to create it)",
            file=sys.stderr,
        )
        return 1

    print(f"opening {db_path} …")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if args.cleanup:
            cleanup_thread(conn, args.thread, args.force)
            conn.commit()
            print("done")
            return 0

        existing_name = get_thread_name(conn, args.thread)
        if existing_name is not None:
            if not args.force and is_protected_name(existing_name):
                print(
                    f"refusing to overwrite thread {args.thread} "
                    f"(name={existing_name!r}): not a test thread. "
                    f"Pass --force to override.",
                    file=sys.stderr,
                )
                return 1
            if args.keep_existing:
                msg_count = conn.execute(
                    "SELECT COUNT(*) FROM conversations WHERE thread_id = ?", (args.thread,)
                ).fetchone()[0]
                if msg_count > 0:
                    print(
                        f"thread {args.thread} already has {msg_count} messages; "
                        f"--keep-existing set, leaving as-is"
                    )
                    return 0
            print(f"  thread {args.thread} exists, wiping + re-seeding")
            conn.execute("DELETE FROM conversations WHERE thread_id = ?", (args.thread,))
            conn.execute("DELETE FROM chat_threads WHERE id = ?", (args.thread,))

        print(
            f"  creating thread id={args.thread} bot={args.bot} name={args.name!r} persona={args.persona}"
        )
        create_thread(conn, args.thread, args.bot, args.name, args.persona)
        print(f"  inserting {args.count} messages …")
        insert_messages(
            conn,
            args.thread,
            args.count,
            start_time=datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC),
        )
        conn.commit()

        # Verify and report.
        cur = conn.execute(
            "SELECT COUNT(*), MIN(id), MAX(id) FROM conversations WHERE thread_id = ?",
            (args.thread,),
        )
        total, min_id, max_id = cur.fetchone()
        print(f"  done: {total} messages, ids {min_id}..{max_id}")
        print(
            f"  open in browser: http://localhost:1421/#/chat?bot={args.bot}&thread={args.thread}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
