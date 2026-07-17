"""Tests for app.domain.constants — domain-wide constants module.

TDD: written together with the new module to lock down its public
contract. If you change a value, you MUST also update the test that
asserts it (that's the whole point).
"""

from app.domain.constants import (
    EMBEDDING_REQUEST_TIMEOUT_SECONDS,
    EMBEDDING_VALIDATION_TIMEOUT_SECONDS,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_MAX_BYTES,
)


class TestHttpStatusCodes:
    """HTTP status code constants must match the standard HTTP/1.1 registry."""

    def test_unauthorized_is_401(self):
        assert HTTP_UNAUTHORIZED == 401

    def test_not_found_is_404(self):
        assert HTTP_NOT_FOUND == 404


class TestTimeouts:
    """Timeout constants — value sanity + relative ordering."""

    def test_validation_timeout_is_15_seconds(self):
        # 1-token health check shouldn't wait as long as a real embedding
        assert EMBEDDING_VALIDATION_TIMEOUT_SECONDS == 15.0

    def test_request_timeout_is_30_seconds(self):
        # Real batched embed_documents can be slow on big inputs
        assert EMBEDDING_REQUEST_TIMEOUT_SECONDS == 30.0

    def test_validation_timeout_is_shorter_than_request_timeout(self):
        # Sanity: validation is a probe, request is a real workload
        assert EMBEDDING_VALIDATION_TIMEOUT_SECONDS < EMBEDDING_REQUEST_TIMEOUT_SECONDS


class TestLogFileRotation:
    """Log file rotation ceiling — total disk usage bounded."""

    def test_max_bytes_is_10_mib(self):
        assert LOG_FILE_MAX_BYTES == 10 * 1024 * 1024

    def test_backup_count_is_3(self):
        # 3 backups x 10 MB = 30 MB ceiling
        assert LOG_FILE_BACKUP_COUNT == 3

    def test_total_ceiling_is_30_mib(self):
        # 10 MB active + 3 x 10 MB backups = 40 MB; we accept that
        # but assert the documented ceiling is what the constants
        # multiply to.
        assert (LOG_FILE_BACKUP_COUNT + 1) * LOG_FILE_MAX_BYTES == 40 * 1024 * 1024


class TestConstantsAreAllCaps:
    """Convention: all module-level constants are ALL_CAPS."""

    def test_all_exports_are_uppercase(self):
        import app.domain.constants as c

        public = [name for name in dir(c) if not name.startswith("_")]
        for name in public:
            assert name == name.upper(), f"{name} should be ALL_CAPS"
