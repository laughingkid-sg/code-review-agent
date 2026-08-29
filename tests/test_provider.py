from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from code_review_agent.env import load_env_file
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
""",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENAI_API_KEY": "existing-key"}, clear=True):
                load_env_file(env_file)

                self.assertEqual(os.environ["OPENAI_BASE_URL"], "https://example.test/v1")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "existing-key")
                self.assertEqual(os.environ["OPENAI_MODEL"], "llm-test")

    def test_openai_compatible_provider_requires_env_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ProviderError, "OPENAI_BASE_URL"):
                OpenAICompatibleProvider.from_env()


if __name__ == "__main__":
    unittest.main()
