from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatResult:
    model: str
    content: str
    usage: dict[str, Any]


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 60
    response_format_mode: str = "json_schema"
    extra_body: dict[str, Any] | None = None

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("OPENAI_MODEL", "").strip()
        response_format_mode = os.environ.get("OPENAI_RESPONSE_FORMAT", "json_schema").strip() or "json_schema"
        extra_body = _extra_body_from_env(os.environ.get("OPENAI_EXTRA_BODY_JSON", ""))
        missing = [
            name
            for name, value in (
                ("OPENAI_BASE_URL", base_url),
                ("OPENAI_API_KEY", api_key),
                ("OPENAI_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise ProviderError(f"Missing required environment variable(s): {', '.join(missing)}")
        if response_format_mode not in {"json_schema", "json_object"}:
            raise ProviderError("OPENAI_RESPONSE_FORMAT must be one of: json_schema, json_object")
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            model=model,
            response_format_mode=response_format_mode,
            extra_body=extra_body,
        )

    def chat(
        self,
        messages: list[ChatMessage],
        max_tokens: int | None = 128,
        temperature: float = 0,
        response_format: dict[str, Any] | None = None,
        top_p: float | None = 1,
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if response_format:
            payload["response_format"] = response_format
        if self.extra_body:
            payload["extra_body"] = self.extra_body

        try:
            response = self._client().chat.completions.create(**payload)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Provider request failed: {exc}") from exc

        choices = _get_value(response, "choices") or []
        if not choices:
            raise ProviderError("Provider response did not include choices.")
        message = _get_value(choices[0], "message") or {}
        content = str(_get_value(message, "content") or "").strip()
        return ChatResult(
            model=str(_get_value(response, "model") or self.model),
            content=content,
            usage=_usage_dict(_get_value(response, "usage")),
        )

    def _client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("OpenAI Python SDK is not installed. Install the `openai` package.") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout_seconds)


def _extra_body_from_env(raw_value: str) -> dict[str, Any] | None:
    value = raw_value.strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ProviderError("OPENAI_EXTRA_BODY_JSON must be a valid JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("OPENAI_EXTRA_BODY_JSON must be a valid JSON object.")
    return parsed


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _usage_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}
