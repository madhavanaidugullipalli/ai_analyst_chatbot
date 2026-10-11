"""Gemini provider via the official Google Gen AI Python SDK (`google-genai`)."""

from __future__ import annotations

from config.settings import settings
from src.llm.base import LLMProvider, LLMResponse


def resolve_gemini_api_key(explicit_key: str | None = None) -> str:
    """Resolve Gemini API key from explicit parameter, Streamlit secrets, env, or settings."""
    if explicit_key is not None:
        return explicit_key.strip()

    # 1. Dynamically inspect Streamlit secrets at runtime (all common TOML layouts)
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            for candidate in ("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"):
                if candidate in st.secrets and str(st.secrets[candidate]).strip():
                    return str(st.secrets[candidate]).strip()
            if "gemini" in st.secrets and hasattr(st.secrets["gemini"], "get"):
                for sub in ("api_key", "API_KEY", "gemini_api_key"):
                    val = st.secrets["gemini"].get(sub)
                    if val and str(val).strip():
                        return str(val).strip()
            if "secrets" in st.secrets and hasattr(st.secrets["secrets"], "get"):
                for sub in ("GEMINI_API_KEY", "gemini_api_key", "api_key"):
                    val = st.secrets["secrets"].get(sub)
                    if val and str(val).strip():
                        return str(val).strip()
    except Exception:
        pass

    # 2. Check settings object
    if getattr(settings, "gemini_api_key", None) and settings.gemini_api_key.strip():
        return settings.gemini_api_key.strip()

    # 3. Check environment variables
    import os

    for env_var in ("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    return ""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self._explicit_key = api_key
        self.model = model or getattr(settings, "gemini_model", "gemini-3.8-flash")
        self.timeout = timeout
        self._client = None

    @property
    def api_key(self) -> str:
        return resolve_gemini_api_key(self._explicit_key)

    @api_key.setter
    def api_key(self, val: str) -> None:
        self._explicit_key = val
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        key = self.api_key
        if not key:
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in Streamlit Secrets or .env."
            )
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=key,
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
