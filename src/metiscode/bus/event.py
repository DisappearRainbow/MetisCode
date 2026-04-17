"""Event definition registry."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(slots=True, frozen=True)
class EventDefinition:
    """Typed event descriptor."""

    type_name: str
    schema: type[BaseModel]


class BusEvent:
    """Factory and registry for bus event definitions."""

    _registry: dict[str, EventDefinition] = {}

    @classmethod
    def define(cls, type_name: str, schema: type[BaseModel]) -> EventDefinition:
        definition = EventDefinition(type_name=type_name, schema=schema)
        cls._registry[type_name] = definition
        return definition

    @classmethod
    def get(cls, type_name: str) -> EventDefinition | None:
        return cls._registry.get(type_name)

    @classmethod
    def all(cls) -> list[EventDefinition]:
        return list(cls._registry.values())
