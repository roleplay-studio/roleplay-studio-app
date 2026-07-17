"""Domain-wide constants — values used across the backend that benefit
from a single, named, import-able reference rather than repeated magic numbers.

Why this file exists:
- Magic numbers (timeouts, HTTP codes) leak across modules → hard to tune
- HTTP status codes (`401`, `404`) read better as `HTTP_UNAUTHORIZED`,
  `HTTP_NOT_FOUND` in error branches
- Domain limits (timeouts, max bytes) can be overridden in tests via
  ``monkeypatch.setattr`` on the module, rather than re-implementing
  the value at every call site

Adding a constant here:
1. Pick a name in ALL_CAPS describing the *what*, not the *value*
   (``EMBEDDING_VALIDATION_TIMEOUT_SECONDS`` > ``TIMEOUT_15``)
2. Add a docstring explaining *why* this value, when to tune it
3. Import from here at the call site, never inline

Test overrides: tests can do
``monkeypatch.setattr("app.domain.constants.EMBEDDING_VALIDATION_TIMEOUT_SECONDS", 0.01)``
to speed up slow test paths.
"""

# ── HTTP status codes ────────────────────────────────────────────────
# Numeric values match the standard HTTP/1.1 registry (RFC 9110).
# Using named constants instead of literals so error branches read like
# English: ``if code == HTTP_UNAUTHORIZED`` vs ``if code == 401``.
HTTP_UNAUTHORIZED: int = 401
HTTP_NOT_FOUND: int = 404

# ── Timeouts (seconds) ──────────────────────────────────────────────
# Validation probe is shorter than the request path — a 1-token health
# check shouldn't wait as long as a real document embedding.
EMBEDDING_VALIDATION_TIMEOUT_SECONDS: float = 15.0

# ── Log file rotation ───────────────────────────────────────────────
# 10 MB x 3 files = 30 MB ceiling. A single chat stream can log hundreds
# of debug chunks; without rotation this would fill the user's disk on
# a misbehaving run.
LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MiB
LOG_FILE_BACKUP_COUNT: int = 3

# ── Embeddings request timeout (seconds) ────────────────────────────
# HttpEmbeddings talks to the user-configured embeddings endpoint. 30 s
# is generous enough for large batched ``embed_documents`` calls without
# hanging forever on a broken endpoint.
EMBEDDING_REQUEST_TIMEOUT_SECONDS: float = 30.0
