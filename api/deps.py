"""FastAPI dependency injection — reuses existing bootstrap."""

from typing import Annotated

from fastapi import Depends

from app.application.container import ApplicationContainer
from app.bootstrap import get_container


def _get_container() -> ApplicationContainer:
    return get_container()


ContainerDep = Annotated[ApplicationContainer, Depends(_get_container)]
