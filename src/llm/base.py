"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str = ""
    provider: str = ""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str) -> LLMResponse:
        """Return model text for a system + user prompt pair."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the provider can accept requests."""
