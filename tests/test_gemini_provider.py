"""Unit checks for Gemini provider wiring (no live API calls)."""

import pytest

from src.llm.api_provider import GeminiProvider, _format_gemini_error
from src.llm.llm_service import LLMService


def test_gemini_unavailable_without_key():
    provider = GeminiProvider(api_key="")
    assert not provider.is_available()
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        provider.complete("system", "user")


def test_llm_service_defaults_to_gemini():
    service = LLMService(provider="gemini", provider_instance=GeminiProvider(api_key=""))
    assert service.provider_name == "gemini"
    assert not service.available
    assert "GEMINI_API_KEY" in service.status_message


def test_unknown_provider_builds_gemini():
    service = LLMService(provider="unknown-xyz")
    assert isinstance(service._provider, GeminiProvider)


def test_format_rate_limit_error():
    msg = _format_gemini_error(RuntimeError("429 RESOURCE_EXHAUSTED rate limit"))
    assert "rate limit" in msg.lower()
