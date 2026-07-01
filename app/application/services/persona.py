import logging

from app.application.dto import UserPersonaDTO
from app.application.exceptions import NotFoundError
from app.application.ports import PersonaRepository

logger = logging.getLogger(__name__)


class PersonaService:
    def __init__(self, personas: PersonaRepository):
        self._personas = personas

    async def create(self, name: str, description: str = "", avatar_path: str | None = None) -> int:
        return await self._personas.create(name.strip(), description.strip(), avatar_path)

    async def update(
        self, persona_id: int, name: str, description: str = "", avatar_path: str | None = None
    ) -> None:
        await self._personas.update(persona_id, name.strip(), description.strip(), avatar_path)

    async def get(self, persona_id: int) -> UserPersonaDTO:
        persona = await self._personas.get(persona_id)
        if persona is None:
            raise NotFoundError(f"Persona {persona_id} was not found")
        return persona

    async def list(self) -> list[UserPersonaDTO]:
        return await self._personas.list()

    async def delete(self, persona_id: int) -> None:
        await self._personas.delete(persona_id)
