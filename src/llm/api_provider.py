"""Gemini provider via the official Google Gen AI Python SDK (`google-genai`)."""

from __future__ import annotations

from config.settings import settings
from src.llm.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.gemini_api_key or "").strip()
        self.model = model or settings.gemini_model
        self.timeout = timeout
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout * 1000)),
            )
        return self._client

    def complete(self, system: str, user: str) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in .env."
            )

        try:
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=self.model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                ),
            )
        except Exception as exc:  # noqa: BLE001 — map SDK/network errors for the UI
            raise RuntimeError(_format_gemini_error(exc)) from exc

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            # Fallback: assemble from candidates if .text is empty
            text = _extract_text(response)
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return LLMResponse(text=text, model=self.model, provider=self.name)


def _extract_text(response) -> str:
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        return "".join(getattr(p, "text", "") or "" for p in parts).strip()
    except Exception:  # noqa: BLE001
        return ""


def _format_gemini_error(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    status = str(getattr(exc, "status", "") or "")

    if (
        code in {429, 503, 504}
        or "429" in message
        or "503" in message
        or "504" in message
        or "resource_exhausted" in lower
        or "high demand" in lower
        or "unavailable" in lower
        or "deadline" in lower
        or "rate" in lower
    ):
        return (
            "Gemini is temporarily unavailable (rate limit or high demand). "
            "Wait a moment and try again, or check your API quota."
        )
    if code in {401, 403} or "api key" in lower or "permission" in lower or "unauthenticated" in lower:
        return (
            "Gemini authentication failed. Check that GEMINI_API_KEY is valid "
            "and enabled for the Gemini API."
        )
    if code == 404 or "not found" in lower:
        return (
            f"Gemini model not found. Check GEMINI_MODEL in .env "
            f"(current setting may be unsupported). Details: {message[:300]}"
        )
    if status:
        return f"Gemini API error ({status}): {message[:400]}"
    return f"Gemini API error: {message[:400]}"


# Alias used by docs / imports
ApiProvider = GeminiProvider
