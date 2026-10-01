from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

#: Transient provider-side conditions worth retrying on the same model.
RETRYABLE_MARKERS = (
    "500",
    "502",
    "503",
    "504",
    "overloaded",
    "unavailable",
    "high demand",
    "deadline",
    "timeout",
    "connection",
    "internal error",
)

#: Conditions that will not clear by retrying. Retrying these only burns quota
#: and delays the caller's fallback, so they fail fast with a specific error.
FATAL_MARKERS = {
    "quota": "LLM_QUOTA_EXHAUSTED",
    "billing": "LLM_QUOTA_EXHAUSTED",
    "resource_exhausted": "LLM_QUOTA_EXHAUSTED",
    "rate limit": "LLM_RATE_LIMITED",
    "429": "LLM_RATE_LIMITED",
    "api key not valid": "LLM_INVALID_KEY",
    "permission denied": "LLM_INVALID_KEY",
    "403": "LLM_INVALID_KEY",
    "not found": "LLM_MODEL_NOT_FOUND",
    "404": "LLM_MODEL_NOT_FOUND",
}


class LLMConfigurationError(RuntimeError):
    """The provider rejected the request in a way retrying cannot fix.

    ``code`` is one of the ``LLM_*`` values above so callers and the API can
    report the exact remediation instead of a generic failure.
    """

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def classify_error(exc: Exception) -> str | None:
    """Return an ``LLM_*`` code when the failure is permanent, else None."""
    message = f"{type(exc).__name__}: {exc}".lower()
    for marker, code in FATAL_MARKERS.items():
        if marker in message:
            return code
    return None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    message = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in message for marker in RETRYABLE_MARKERS)


class LLMUnavailableError(RuntimeError):
    """Raised when no configured LLM provider could be reached."""


class LLMConfigurationError(LLMUnavailableError):
    """The provider rejected the request in a way retrying cannot fix.

    ``code`` is one of the ``LLM_*`` values above so callers and the API can
    report the exact remediation instead of a generic failure. It subclasses
    :class:`LLMUnavailableError`, so every existing fallback still catches it.
    """

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class LLMClient:
    """Thin, retrying client over the configured LLM provider.

    The client never fabricates structured output. When the provider cannot be
    reached it raises :class:`LLMUnavailableError` so callers can fall back to
    an explicitly labelled deterministic path instead of silently receiving a
    made-up answer.
    """

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = (provider or settings.LLM_PROVIDER or "gemini").lower()
        self.model = model or settings.LLM_MODEL or "gemini-3.8-flash"
        self.last_error: str | None = None
        self.last_error_code: str | None = None

    # ------------------------------------------------------------------
    # availability
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        if self.provider in {"gemini", "google", "google-genai"}:
            return bool(settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY)
        if self.provider == "openai":
            return bool(settings.OPENAI_API_KEY)
        return False

    def _model_candidates(self) -> list[str]:
        candidates = [self.model]
        for fallback in settings.LLM_FALLBACK_MODELS or []:
            if fallback and fallback not in candidates:
                candidates.append(fallback)
        return candidates

    def _dispatch(self, prompt: str, system_prompt: str | None, kwargs: dict[str, Any]) -> str:
        if not self.is_configured():
            raise LLMUnavailableError(
                f"No API key configured for LLM provider '{self.provider}'."
            )
        if self.provider in {"gemini", "google", "google-genai"}:
            return self._generate_gemini(prompt, system_prompt=system_prompt, **kwargs)
        if self.provider == "openai":
            return self._generate_openai(prompt, system_prompt=system_prompt, **kwargs)
        raise LLMUnavailableError(
            f"Unsupported LLM provider '{self.provider}'. Use 'gemini' or 'openai'."
        )

    def _call_with_retry(self, prompt: str, system_prompt: str | None, kwargs: dict[str, Any]) -> str:
        attempts = max(1, int(settings.LLM_MAX_ATTEMPTS))
        backoff = max(0.0, float(settings.LLM_RETRY_BACKOFF_SECONDS))
        last_exc: Exception | None = None

        for model in self._model_candidates():
            self.model = model
            for attempt in range(1, attempts + 1):
                try:
                    return self._dispatch(prompt, system_prompt, dict(kwargs, model=model))
                except Exception as exc:  # noqa: BLE001 - provider errors are not uniform
                    last_exc = exc
                    # Quota, key, and model problems will not clear by retrying, and
                    # trying every fallback model would only repeat the same failure.
                    code = classify_error(exc)
                    if code is not None:
                        self.last_error = f"{type(exc).__name__}: {exc}"
                        self.last_error_code = code
                        raise LLMConfigurationError(code, self.last_error)
                    if not _is_retryable(exc):
                        self.last_error = f"{type(exc).__name__}: {exc}"
                        break
                    if attempt < attempts:
                        time.sleep(backoff * attempt)

        self.last_error = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown LLM failure"
        raise LLMUnavailableError(
            f"LLM provider '{self.provider}' could not be reached: {self.last_error}"
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def generate(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        return self._call_with_retry(prompt, system_prompt, kwargs)

    def generate_structured(
        self, schema: type[T], prompt: str, *, system_prompt: str | None = None, **kwargs: Any
    ) -> T:
        instruction = system_prompt or "Respond with valid JSON matching the requested schema and nothing else."
        raw = self.generate(prompt, system_prompt=instruction, **kwargs)
        content = (raw or "").strip()
        if not content:
            raise LLMUnavailableError("LLM returned an empty response.")
        if content.startswith("```"):
            content = content.strip("`")
            _, _, content = content.partition("\n")
            content = content.rsplit("```", 1)[0]
        try:
            return schema.model_validate_json(content)
        except (ValidationError, ValueError):
            pass
        try:
            return schema.model_validate(json.loads(content))
        except (ValidationError, ValueError) as exc:
            raise LLMUnavailableError(f"LLM response did not match {schema.__name__}: {exc}") from exc

    # ------------------------------------------------------------------
    # providers
    # ------------------------------------------------------------------
    def _generate_gemini(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - environment protection
            raise LLMUnavailableError(
                "The google-genai package is not installed. Install backend requirements."
            ) from exc

        api_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        if not api_key:
            raise LLMUnavailableError("Set GEMINI_API_KEY or GOOGLE_API_KEY to use live LLM reasoning.")

        model = str(kwargs.get("model") or self.model)
        client = genai.Client(api_key=api_key)
        full_prompt = prompt if system_prompt is None else f"{system_prompt}\n\n{prompt}"
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config={"temperature": float(kwargs.get("temperature", 0.0))},
        )
        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()

        candidates = getattr(response, "candidates", None)
        if candidates:
            content = getattr(candidates[0], "content", None)
            if content is not None:
                parts = getattr(content, "parts", []) or []
                assembled = "".join(getattr(part, "text", "") for part in parts)
                if assembled.strip():
                    return assembled.strip()
        raise LLMUnavailableError(f"Gemini model '{model}' returned no content.")

    def _generate_openai(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment protection
            raise LLMUnavailableError("The OpenAI SDK is not installed.") from exc

        if not settings.OPENAI_API_KEY:
            raise LLMUnavailableError("OPENAI_API_KEY is not configured.")

        model = str(kwargs.get("model") or self.model)
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt or "Return concise fact-checking guidance."},
                {"role": "user", "content": prompt},
            ],
            temperature=float(kwargs.get("temperature", 0.0)),
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMUnavailableError(f"OpenAI model '{model}' returned no content.")
        return content.strip()


_REMEDIATION = {
    "LLM_QUOTA_EXHAUSTED": (
        "The provider quota for this API key is exhausted. Wait for the quota to reset, "
        "enable billing on the provider account, or set a different API key in .env."
    ),
    "LLM_RATE_LIMITED": "The provider is rate limiting this key. Reduce request volume or use another key.",
    "LLM_INVALID_KEY": "The API key was rejected. Check GEMINI_API_KEY or OPENAI_API_KEY in .env.",
    "LLM_MODEL_NOT_FOUND": "The configured model is unavailable. Set a current LLM_MODEL in .env.",
    "LLM_NOT_CONFIGURED": "No API key is configured. Set GEMINI_API_KEY or OPENAI_API_KEY in .env.",
    "LLM_UNREACHABLE": "The provider could not be reached. Check network access and retry.",
}


def llm_diagnostics(probe: bool = True) -> dict[str, Any]:
    """Report whether live reasoning is available, and exactly what to fix if not."""
    client = LLMClient()
    info: dict[str, Any] = {
        "provider": client.provider,
        "model": settings.LLM_MODEL,
        "fallback_models": list(settings.LLM_FALLBACK_MODELS or []),
        "key_configured": client.is_configured(),
        "available": False,
        "error_code": None,
        "error": None,
        "remediation": None,
    }

    if not client.is_configured():
        info["error_code"] = "LLM_NOT_CONFIGURED"
        info["remediation"] = _REMEDIATION["LLM_NOT_CONFIGURED"]
        return info

    if not probe:
        info["available"] = True
        return info

    try:
        client.generate("Reply with the single word OK.")
        info["available"] = True
    except LLMConfigurationError as exc:
        info["error_code"] = exc.code
        info["error"] = exc.detail
        info["remediation"] = _REMEDIATION.get(exc.code, "Check the provider configuration.")
    except LLMUnavailableError as exc:
        info["error_code"] = "LLM_UNREACHABLE"
        info["error"] = str(exc)
        info["remediation"] = _REMEDIATION["LLM_UNREACHABLE"]
    except Exception as exc:  # noqa: BLE001 - diagnostics must never raise
        info["error_code"] = "LLM_UNREACHABLE"
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["remediation"] = _REMEDIATION["LLM_UNREACHABLE"]
    return info


llm = LLMClient()
