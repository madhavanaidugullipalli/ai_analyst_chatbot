"""LLM service facade — Gemini is the active default provider."""

from __future__ import annotations

from typing import Optional

from config.settings import settings
from src.llm.api_provider import GeminiProvider
from src.llm.base import LLMProvider, LLMResponse
from src.llm.ollama_provider import OllamaProvider
from src.llm.prompts import (
    EXPLANATION_SYSTEM_PROMPT,
    SQL_SYSTEM_PROMPT,
    build_explanation_prompt,
    build_sql_user_prompt,
)


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM provider is usable."""


class LLMService:
    def __init__(
        self,
        provider: Optional[str] = None,
        provider_instance: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ) -> None:
        self.provider_name = (provider or settings.llm_provider).lower()
        self.api_key = api_key
        self.ollama_base_url = (ollama_base_url or settings.ollama_base_url).rstrip("/")
        self.ollama_model = ollama_model or settings.ollama_model
        self._provider = provider_instance or self._build_provider(
            self.provider_name,
            api_key=api_key,
            ollama_base_url=self.ollama_base_url,
            ollama_model=self.ollama_model,
        )

    @staticmethod
    def _build_provider(
        name: str,
        api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ) -> Optional[LLMProvider]:
        if name in {"none", "off", "disabled"}:
            return None
        if name == "ollama":
            return OllamaProvider(base_url=ollama_base_url, model=ollama_model)
        # Default / unknown → Gemini (active provider)
        return GeminiProvider(api_key=api_key)

    @property
    def available(self) -> bool:
        if self._provider is None:
            return False
        return self._provider.is_available()

    @property
    def status_message(self) -> str:
        if self.provider_name in {"none", "off", "disabled"}:
            return "LLM disabled (LLM_PROVIDER=none)."
        if self._provider is None:
            return "No LLM provider configured."
        if self.provider_name == "ollama":
            url = getattr(self._provider, "base_url", self.ollama_base_url)
            model = getattr(self._provider, "model", self.ollama_model)
            if self.available:
                return f"Ollama ready ({model} at {url})."
            return (
                f"Ollama is not reachable at {url}. "
                "Ensure Ollama is running (or provide a public tunnel URL on mobile/cloud)."
            )
        if self.provider_name == "gemini" or isinstance(self._provider, GeminiProvider):
            if self.available:
                return f"Gemini ready ({settings.gemini_model})."
            return "GEMINI_API_KEY is missing. Enter it in the sidebar or add it to Streamlit Secrets / .env."
        return f"Provider '{self.provider_name}' is not available."

    def complete(self, system: str, user: str) -> LLMResponse:
        if not self.available or self._provider is None:
            raise LLMUnavailableError(self.status_message)
        return self._provider.complete(system, user)

    def generate_sql(self, schema_text: str, question: str, history: str = "") -> str:
        user = build_sql_user_prompt(schema_text, question, history)
        return self.complete(SQL_SYSTEM_PROMPT, user).text

    def explain_result(self, question: str, sql: str, result_preview: str) -> str:
        user = build_explanation_prompt(question, sql, result_preview)
        return self.complete(EXPLANATION_SYSTEM_PROMPT, user).text
