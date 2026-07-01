"""Domain-level exceptions.

Domain has no outward dependencies — it does not import from
``application`` or ``infrastructure``. By living here, exception
classes can be raised by any layer without creating circular imports.

Used by m3 in docs/review.md: moves ``ConfigurationError`` out of
``app.application.exceptions`` (which produced an
``infrastructure → application`` cycle when ``infrastructure.config``
needed to raise it) and into the layer that's a legal dependency
target for everyone.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain-level failures."""


class ConfigurationError(DomainError):
    """Required configuration is missing or invalid.

    Raised by ``app.infrastructure.config`` when an env var is missing
    or a value fails validation, and by ``app.application.services`` when
    a service discovers its config is unsatisfiable at runtime.
    """


__all__ = ["ConfigurationError", "DomainError"]
