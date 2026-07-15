"""Provider: ``custom`` — user-supplied OpenAI-compatible endpoint.

The ``custom`` provider doesn't have its own wire-protocol subclass;
it reuses the generic :class:`BaseOpenAICompatibleLLM` machinery
with whatever ``base_url`` and ``model`` the operator pastes into
the SetupWizard. Both are required at configure time (the catalog
leaves them empty), and the bootstrap factory instantiates a
:class:`BaseOpenAICompatibleLLM` directly for ``custom``.

We still publish a :class:`ProviderCatalog` entry so the SetupWizard
dropdown lists ``custom`` alongside the other provider ids and the
``/api/setup/providers`` endpoint returns a complete catalog. The
catalog's ``default_base_url`` and ``default_model`` are empty by
design — the wizard forces the operator to fill both in.
"""

from __future__ import annotations

from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM
from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
)

catalog = ProviderCatalog(
    provider_id="custom",
    label="Custom",
    description="Any OpenAI-compatible API",
    default_base_url="",
    default_model="",
    # Empty by design — operators paste whatever the third-party
    # server expects. Keeping the tuple empty is the documented
    # signal for the wizard to render a free-text model input.
    available_models=(),
    needs_key=False,
    manual_setup=False,
)


class CustomLLM(BaseOpenAICompatibleLLM):
    """OpenAI-compatible user-supplied endpoint.

    The bootstrap factory handles the ``custom`` case directly in
    :mod:`app.infrastructure.llm.factory` (instantiates the base class
    with whatever ``base_url`` / ``model`` the operator pasted). We
    declare the class anyway so :class:`ProviderLLM` discovery keeps
    a stable shape across every id.
    """

    provider_id = "custom"
    catalog = catalog
