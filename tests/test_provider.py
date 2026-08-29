from pathlib import Path
import os
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from code_review_agent.env import load_env_file
from code_review_agent.providers import ChatMessage
from code_review_agent.providers import OpenAICompatibleProvider, ProviderError


class ProviderConfigTest(unittest.TestCase):
    def test_load_env_file_sets_missing_values_and_preserves_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                """
OPENAI_BASE_URL="https://example.test/v1"
OPENAI_API_KEY=file-key
OPENAI_MODEL='llm-test'
OPENAI_EXTRA_BODY_JSON='{"enable_thinking": false}'
""",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENAI_API_KEY": "existing-key"}, clear=True):
                load_env_file(env_file)

                self.assertEqual(os.environ["OPENAI_BASE_URL"], "https://example.test/v1")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "existing-key")
                self.assertEqual(os.environ["OPENAI_MODEL"], "llm-test")
                self.assertEqual(os.environ["OPENAI_EXTRA_BODY_JSON"], '{"enable_thinking": false}')

    def test_openai_compatible_provider_requires_env_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ProviderError, "OPENAI_BASE_URL"):
                OpenAICompatibleProvider.from_env()

    def test_openai_compatible_provider_reads_response_format_mode(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://example.test/v1",
                "OPENAI_API_KEY": "key",
                "OPENAI_MODEL": "llm-test",
                "OPENAI_RESPONSE_FORMAT": "json_object",
            },
            clear=True,
        ):
            provider = OpenAICompatibleProvider.from_env()

        self.assertEqual(provider.response_format_mode, "json_object")

    def test_openai_compatible_provider_reads_extra_body_json(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://example.test/v1",
                "OPENAI_API_KEY": "key",
                "OPENAI_MODEL": "llm-test",
                "OPENAI_EXTRA_BODY_JSON": '{"enable_thinking": false}',
            },
            clear=True,
        ):
            provider = OpenAICompatibleProvider.from_env()

        self.assertEqual(provider.extra_body, {"enable_thinking": False})

    def test_openai_compatible_provider_rejects_invalid_extra_body_json(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://example.test/v1",
                "OPENAI_API_KEY": "key",
                "OPENAI_MODEL": "llm-test",
                "OPENAI_EXTRA_BODY_JSON": "[]",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ProviderError, "OPENAI_EXTRA_BODY_JSON"):
                OpenAICompatibleProvider.from_env()

    def test_openai_compatible_provider_rejects_invalid_response_format_mode(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "https://example.test/v1",
                "OPENAI_API_KEY": "key",
                "OPENAI_MODEL": "llm-test",
                "OPENAI_RESPONSE_FORMAT": "xml",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ProviderError, "OPENAI_RESPONSE_FORMAT"):
                OpenAICompatibleProvider.from_env()

    def test_chat_can_request_json_object_response_format(self) -> None:
        client = _FakeClient()
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1",
            api_key="key",
            model="llm-test",
            extra_body={"enable_thinking": False},
        )
        with patch.object(OpenAICompatibleProvider, "_client", return_value=client):
            result = provider.chat(
                [ChatMessage(role="user", content="Return JSON.")],
                max_tokens=44,
                temperature=0,
                response_format={"type": "json_object"},
            )

        self.assertEqual(result.content, "{}")
        self.assertEqual(result.model, "llm-test")
        self.assertEqual(result.usage, {"total_tokens": 3})
        self.assertEqual(
            client.calls,
            [
                {
                    "model": "llm-test",
                    "messages": [{"role": "user", "content": "Return JSON."}],
                    "temperature": 0,
                    "max_tokens": 44,
                    "top_p": 1,
                    "response_format": {"type": "json_object"},
                    "extra_body": {"enable_thinking": False},
                }
            ],
        )

    def test_chat_wraps_sdk_errors(self) -> None:
        provider = OpenAICompatibleProvider(base_url="https://example.test/v1", api_key="key", model="llm-test")
        with patch.object(OpenAICompatibleProvider, "_client", return_value=_FakeClient(error=RuntimeError("boom"))):
            with self.assertRaisesRegex(ProviderError, "Provider request failed"):
                provider.chat([])


class _FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        usage = SimpleNamespace(model_dump=lambda: {"total_tokens": 3})
        message = SimpleNamespace(content="{}")
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(model="llm-test", choices=[choice], usage=usage)


if __name__ == "__main__":
    unittest.main()
