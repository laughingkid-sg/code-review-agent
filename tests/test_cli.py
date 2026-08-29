from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_review_agent.cli import main
from code_review_agent.providers import ChatResult


class CliTest(unittest.TestCase):
    def test_code_rules_dry_run_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            kb = root / "knowledgebase"
            repo.mkdir()
            (repo / ".code-review.yml").write_text(_config(), encoding="utf-8")
            handler = repo / "demo-projects" / "simple-api" / "internal" / "handler"
            handler.mkdir(parents=True)
            target = handler / "product.go"
            target.write_text(
                """package handler

func create() {
	if err := decoder.Decode(&req); err != nil {
		writeError(err)
	}
	save(req)
}
""",
                encoding="utf-8",
            )
            rules = kb / "demo" / "demo-project" / "go"
            rules.mkdir(parents=True)
            (rules / "RULES.md").write_text(_project_rule(), encoding="utf-8")

            output = repo / ".code-review" / "artifacts" / "code-rules-review.md"
            exit_code = main(
                [
                    "run",
                    "--mode",
                    "code-rules",
                    "--repository",
                    str(repo),
                    "--knowledgebase",
                    str(kb),
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = output.read_text(encoding="utf-8")
            self.assertIn("GO-DEMO-PROJ-001", report)
            self.assertIn("Handler continues after request parsing failure", report)

    def test_business_rules_dry_run_writes_summary_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".code-review.yml").write_text(_config(), encoding="utf-8")
            docs = repo / "demo-projects" / "simple-api" / "docs"
            docs.mkdir(parents=True)
            (docs / "PRD.md").write_text("# Product Catalog\n\n## Create Product\n", encoding="utf-8")
            (docs / "TDD.md").write_text("# Technical Design\n\n## Handler Layer\n", encoding="utf-8")

            output = repo / ".code-review" / "artifacts" / "business-rules-review.md"
            exit_code = main(
                [
                    "run",
                    "--mode",
                    "business-rules",
                    "--repository",
                    str(repo),
                    "--knowledgebase",
                    str(root / "knowledgebase"),
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            summary = repo / ".code-review" / "artifacts" / "simple-api-prd-td-summary.md"
            self.assertIn("Create Product", summary.read_text(encoding="utf-8"))

    def test_qwen_code_rules_writes_provider_review_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            kb = root / "knowledgebase"
            repo.mkdir()
            (repo / ".code-review.yml").write_text(_config(), encoding="utf-8")
            handler = repo / "demo-projects" / "simple-api" / "internal" / "handler"
            handler.mkdir(parents=True)
            target = handler / "product.go"
            target.write_text("package handler\n", encoding="utf-8")
            rules = kb / "demo" / "demo-project" / "go"
            rules.mkdir(parents=True)
            (rules / "RULES.md").write_text(_project_rule(), encoding="utf-8")
            provider = _FakeProvider()

            output = repo / ".code-review" / "artifacts" / "code-rules-review.md"
            with patch("code_review_agent.cli.OpenAICompatibleProvider.from_env", return_value=provider):
                exit_code = main(
                    [
                        "run",
                        "--mode",
                        "code-rules",
                        "--repository",
                        str(repo),
                        "--knowledgebase",
                        str(kb),
                        "--output",
                        str(output),
                        "--provider",
                        "qwen",
                        "--changed-file",
                        str(target),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("provider finding", output.read_text(encoding="utf-8"))
            audit = repo / "output" / "code-rules-review.md"
            self.assertIn("Provider Transcript", audit.read_text(encoding="utf-8"))

    def test_qwen_business_rules_reuses_fresh_summary_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".code-review.yml").write_text(_config(), encoding="utf-8")
            docs = repo / "demo-projects" / "simple-api" / "docs"
            docs.mkdir(parents=True)
            (docs / "PRD.md").write_text("# Product Catalog\n", encoding="utf-8")
            (docs / "TDD.md").write_text("# Technical Design\n", encoding="utf-8")
            handler = repo / "demo-projects" / "simple-api" / "internal" / "handler"
            handler.mkdir(parents=True)
            target = handler / "product.go"
            target.write_text("package handler\n", encoding="utf-8")
            summary = repo / ".code-review" / "artifacts" / "simple-api-prd-td-summary.md"
            summary.parent.mkdir(parents=True)
            summary.write_text("# Cached Summary\n", encoding="utf-8")
            provider = _FakeProvider()

            output = repo / ".code-review" / "artifacts" / "business-rules-review.md"
            with patch("code_review_agent.cli.OpenAICompatibleProvider.from_env", return_value=provider):
                exit_code = main(
                    [
                        "run",
                        "--mode",
                        "business-rules",
                        "--repository",
                        str(repo),
                        "--knowledgebase",
                        str(root / "knowledgebase"),
                        "--output",
                        str(output),
                        "--provider",
                        "qwen",
                        "--changed-file",
                        str(target),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(provider.calls, 1)
            self.assertEqual(summary.read_text(encoding="utf-8"), "# Cached Summary\n")
            self.assertFalse((repo / "output" / "business-summary-simple-api.md").exists())
            self.assertTrue((repo / "output" / "business-review-simple-api.md").exists())

    def test_aggregate_combines_input_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".code-review.yml").write_text(_config(), encoding="utf-8")
            code_review = repo / "code-rules-review.md"
            business_review = repo / "business-rules-review.md"
            code_review.write_text("# Code\n\n### Code finding\n", encoding="utf-8")
            business_review.write_text("# Business\n\n### Business finding\n", encoding="utf-8")
            output = repo / ".code-review" / "artifacts" / "aggregate-review.md"

            exit_code = main(
                [
                    "run",
                    "--mode",
                    "aggregate",
                    "--repository",
                    str(repo),
                    "--knowledgebase",
                    str(root / "knowledgebase"),
                    "--output",
                    str(output),
                    "--aggregate-input",
                    str(code_review),
                    "--aggregate-input",
                    str(business_review),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = output.read_text(encoding="utf-8")
            self.assertIn("Code finding", report)
            self.assertIn("Business finding", report)


def _config() -> str:
    return """version: 1
repository:
  name: code-review-demo
  department: demo
  project: demo-project
  languages:
    - go
knowledge:
  layers:
    - demo/demo-project/go
  disabled_rules: []
documents:
  summary_artifact_dir: .code-review/artifacts
  sets:
    - id: simple-api
      name: Simple API
      paths:
        prd: demo-projects/simple-api/docs/PRD.md
        td: demo-projects/simple-api/docs/TDD.md
      code_paths:
        - demo-projects/simple-api
reviews:
  code_rules:
    output: .code-review/artifacts/code-rules-review.md
  business_rules:
    output: .code-review/artifacts/business-rules-review.md
github:
  comment_mode: dry_run
"""


def _project_rule() -> str:
    return """# Demo Project Go Rules

## [Do not continue after request binding or decode failures](#stop-after-request-binding-failure)

| Field | Value |
| --- | --- |
| ID | `GO-DEMO-PROJ-001` |
| Slug | `stop-after-request-binding-failure` |
| Contributor | `example@gmail.com` |
| Severity | `P1` |

### Rule

Handlers must stop processing after request binding, JSON decoding, or path/query parsing fails.
"""


class _FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, *_args, **_kwargs) -> ChatResult:
        self.calls += 1
        return ChatResult(model="fake-qwen", content="provider finding", usage={"total_tokens": 3})


if __name__ == "__main__":
    unittest.main()
