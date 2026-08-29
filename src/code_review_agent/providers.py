from __future__ import annotations

from dataclasses import dataclass
import json
import os
import ssl
from typing import Any
from urllib import error, request


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

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("OPENAI_MODEL", "").strip()
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
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model)

    def chat(
        self,
        messages: list[ChatMessage],
        max_tokens: int = 128,
        temperature: float = 0,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        response = self._post_json("/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise ProviderError("Provider response did not include choices.")
        message = choices[0].get("message") or {}
        content = str(message.get("content", "")).strip()
        return ChatResult(model=str(response.get("model", self.model)), content=content, usage=response.get("usage", {}))

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        context = _ssl_context()
        try:
            with request.urlopen(req, timeout=self.timeout_seconds, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Provider HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise ProviderError(f"Provider request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("Provider response was not valid JSON.") from exc


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())
