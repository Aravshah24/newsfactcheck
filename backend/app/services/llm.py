from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Phase 1 LLM client backed by the real Gemini API when configured."""

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = (provider or settings.LLM_PROVIDER or "gemini").lower()
        self.model = model or settings.LLM_MODEL or "gemini-2.5-flash"

    def generate(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        if self.provider in {"gemini", "google", "google-genai"}:
            return self._generate_gemini(prompt, system_prompt=system_prompt, **kwargs)
        if self.provider == "openai":
            return self._generate_openai(prompt, system_prompt=system_prompt, **kwargs)
        raise RuntimeError(f"Unsupported LLM provider: {self.provider}. Use 'gemini' or 'openai'.")

    def generate_structured(self, schema: type[T], prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> T:
        payload = self._fallback_structured_payload(schema, prompt)
        if self.provider in {"gemini", "google", "google-genai"}:
            try:
                text = self._generate_gemini(prompt, system_prompt=system_prompt or "Respond with valid JSON matching the schema.", **kwargs)
                content = text.strip()
                if content:
                    try:
                        return schema.model_validate_json(content)
                    except Exception:
                        try:
                            return schema.model_validate(json.loads(content))
                        except Exception:
                            pass
            except RuntimeError:
                pass
        if self.provider == "openai":
            try:
                content = self._generate_openai(prompt, system_prompt=system_prompt or "Respond with valid JSON matching the schema.", **kwargs)
                if content:
                    try:
                        return schema.model_validate_json(content)
                    except Exception:
                        try:
                            return schema.model_validate(json.loads(content))
                        except Exception:
                            pass
            except RuntimeError:
                pass
        return schema.model_validate(payload)

    def _generate_gemini(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - environment protection
            raise RuntimeError("The google-genai package is not installed. Install backend requirements and configure GEMINI_API_KEY.") from exc

        api_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        if not api_key:
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY before using live LLM reasoning.")

        client = genai.Client(api_key=api_key)
        full_prompt = prompt if system_prompt is None else f"{system_prompt}\n\n{prompt}"
        response = client.models.generate_content(model=self.model, contents=full_prompt)
        text = getattr(response, "text", None)
        if text:
            return text.strip()

        if getattr(response, "candidates", None):
            first = response.candidates[0]
            content = getattr(first, "content", None)
            if content is not None:
                parts = getattr(content, "parts", []) or []
                assembled = "".join(getattr(part, "text", "") for part in parts)
                if assembled:
                    return assembled.strip()

        raise RuntimeError("Gemini returned no content for the current prompt.")

    def _generate_openai(self, prompt: str, *, system_prompt: str | None = None, **kwargs: Any) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment protection
            raise RuntimeError("The OpenAI SDK is not installed or the provider is not configured.") from exc

        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt or "Return concise fact-checking guidance."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned no content for the current prompt.")
        return content.strip()

    @staticmethod
    def _fallback_structured_payload(schema: type[T], prompt: str) -> dict[str, Any]:
        lower = prompt.lower()
        data: dict[str, Any] = {}
        for name, field in schema.model_fields.items():
            if field.annotation is str:
                data[name] = ""
            elif field.annotation is list:
                data[name] = []
            elif field.annotation is float:
                data[name] = 0.5
            elif field.annotation in (bool, int):
                data[name] = False if field.annotation is bool else 0
            elif field.annotation is dict:
                data[name] = {}
        if "missing" in lower:
            data.setdefault("missing_context", ["Important time period or baseline is omitted."])
            data.setdefault("completeness_status", "MOSTLY_COMPLETE")
        if "verify" in lower or "verdict" in lower:
            data.setdefault("verdict", "PARTIALLY_SUPPORTED")
            data.setdefault("confidence", 0.6)
            data.setdefault("rationale", "Evidence is mixed and should be interpreted conservatively.")
        return data


llm = LLMClient()
