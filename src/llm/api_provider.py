"""Gemini provider via the official Google Gen AI Python SDK (`google-genai`)."""

from __future__ import annotations

from config.settings import settings
from src.llm.base import LLMProvider, LLMResponse


import os
import re
from pathlib import Path

FALLBACK_MODELS = ("gemini-3.5-flash", "gemini-3.5-flash-lite")


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
    for env_var in ("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    # 4. Fallback: check .streamlit/secrets.toml directly in case TOML parsing failed
    for secrets_path in (
        Path(".streamlit/secrets.toml"),
        Path.home() / ".streamlit" / "secrets.toml",
    ):
        try:
            if secrets_path.is_file():
                content = secrets_path.read_text(encoding="utf-8")
                match = re.search(
                    r'(?:GEMINI_API_KEY|GOOGLE_API_KEY|api_key)\s*=\s*["\']?([a-zA-Z0-9_\-\.]+)',
                    content,
                    re.IGNORECASE,
                )
                if match:
                    return match.group(1).strip()
        except Exception:
            pass

    return ""


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._explicit_key = api_key
        raw_model = model or getattr(settings, "gemini_model", "gemini-3.5-flash")
        if raw_model in {"gemini-3.8-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"}:
            raw_model = "gemini-3.5-flash"
        self.model = raw_model
        self.timeout = min(timeout, 20.0)
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

    def test_connection(self) -> tuple[bool, str]:
        """Test API key validity with a lightweight prompt. Returns (success, message)."""
        if not self.is_available():
            return False, "Gemini API key is not configured."
        try:
            client = self._get_client()
            models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
            last_err = None
            for m in models_to_try:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents="ping",
                    )
                    if getattr(resp, "text", None):
                        return True, f"Key verified and working ({m})."
                except Exception as inner:
                    last_err = inner
                    code = getattr(inner, "code", None) or getattr(inner, "status_code", None)
                    if code in {401, 403} or "unauthenticated" in str(inner).lower():
                        return False, _format_gemini_error(inner)
                    continue
            if last_err:
                return False, _format_gemini_error(last_err)
            return True, "Key verified."
        except Exception as exc:
            return False, _format_gemini_error(exc)

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

        client = self._get_client()
        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        last_exception = None

        for attempt_model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=attempt_model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.1,
                    ),
                )
                text = (getattr(response, "text", None) or "").strip()
                if not text:
                    text = _extract_text(response)
                if text:
                    return LLMResponse(text=text, model=attempt_model, provider=self.name)
            except Exception as exc:
                last_exception = exc
                err_str = str(exc).lower()
                # If authentication failed, no point retrying other models
                if "401" in err_str or "403" in err_str or "unauthenticated" in err_str:
                    raise RuntimeError(_format_gemini_error(exc)) from exc
                # For 503, 504, 404, try next fallback model
                continue

        if last_exception:
            raise RuntimeError(_format_gemini_error(last_exception)) from last_exception
        raise RuntimeError("Gemini returned an empty response.")


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

    if "resource_exhausted" in lower or "quota" in lower:
        return (
            "Gemini API Quota Exceeded (429 RESOURCE_EXHAUSTED rate limit). "
            f"Your Google account's rate limit was reached. Details: {message[:180]}"
        )
    if (
        code in {429, 503, 504}
        or "429" in message
        or "503" in message
        or "504" in message
        or "high demand" in lower
        or "unavailable" in lower
        or "deadline" in lower
    ):
        return (
            f"Gemini server busy or timed out (Code {code or '504'}). "
            f"Details: {message[:180]}"
        )
    if code in {401, 403} or "api key" in lower or "permission" in lower or "unauthenticated" in lower:
        return (
            "Gemini authentication failed. Check that GEMINI_API_KEY is valid "
            f"and enabled for the Gemini API. Details: {message[:180]}"
        )
    if code == 404 or "not found" in lower:
        return f"Gemini model not found (404). Details: {message[:180]}"
    if status:
        return f"Gemini API error ({status}): {message[:250]}"
    return f"Gemini API error: {message[:250]}"


# Alias used by docs / imports
ApiProvider = GeminiProvider
