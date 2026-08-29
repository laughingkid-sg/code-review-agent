from pathlib import Path
import tempfile
import unittest

from code_review_agent.cli import main


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


if __name__ == "__main__":
    unittest.main()
