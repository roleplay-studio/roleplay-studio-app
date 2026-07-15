"""Provider: LM Studio (local server, no auth).

Endpoint: ``http://localhost:1234/v1`` by default. LM Studio ships
a built-in OpenAI-compatible server; the model id field is whatever
the user has loaded in the Studio UI today, so we leave it empty
and let the operator pick from the dropdown of currently-loaded
models — LM Studio exposes ``/v1/models`` for that.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="lm-studio",
    label="LM Studio",
    description="Local models via LM Studio",
    default_base_url="http://localhost:1234/v1",
    default_model="",
    # ``available_models`` is empty by design — LM Studio serves
    # whatever models the operator has loaded in the Studio UI. The
    # wizard's model field falls back to a free-text input when this
    # list is empty.
    available_models=(),
    needs_key=False,
    manual_setup=False,
)


class LMStudioLLM(ProviderLLM):
    provider_id = "lm-studio"
    catalog = catalog
