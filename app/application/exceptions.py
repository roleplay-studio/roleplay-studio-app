"""Application-level exceptions suitable for presentation adapters.

.. note::
   ``ConfigurationError`` was historically co-located here, but
   ``app.application`` must not import from ``app.infrastructure`` and
   ``app.infrastructure`` must not import from ``app.application`` (m3
   in docs/review.md). The class now lives in ``app.domain.exceptions``
   (domain has no outward dependencies), and is re-exported below for
   backward compat with code that still does
   ``from app.application.exceptions import ConfigurationError``.
"""

from app.domain.exceptions import ConfigurationError as _ConfigurationError

__all__ = [
    "ApplicationError",
    "ConfigurationError",
    "ExternalServiceError",
    "NotFoundError",
    "UploadError",
    "ValidationError",
]


class ApplicationError(Exception):
    """Base class for expected application failures."""


class NotFoundError(ApplicationError):
    """Requested entity does not exist."""


class ValidationError(ApplicationError):
    """Input failed application validation.

    Carries an optional ``http_status`` hint so the presentation layer
    can map a 400 vs a 413 (payload too large) without sniffing the
    message. Defaults to 400.
    """

    def __init__(self, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


class ExternalServiceError(ApplicationError):
    """External service failed or returned an unusable response."""


class UploadError(ValidationError):
    """Upload-specific validation failure.

    Raised by ``UploadService`` for any user-input problem (missing
    filename, wrong extension, payload too large, …). The presentation
    layer maps this to the appropriate HTTP status from ``http_status``.
    Carries a stable error code so the client can branch on it without
    parsing the message.
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: int = 400,
        code: str = "upload_error",
    ) -> None:
        super().__init__(message, http_status=http_status)
        self.code = code


# Re-exported alias for backward compat — see module docstring.
ConfigurationError = _ConfigurationError
