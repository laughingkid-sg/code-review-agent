from pathlib import Path
import tempfile
import unittest

from code_review_agent.rules import load_rules, parse_rules_file


class RuleParsingTest(unittest.TestCase):
    def test_parse_pure_markdown_rule_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "RULES.md"
            path.write_text(
                """# Rules

## GO-COM-001: Return errors with context

| Field | Value |
| --- | --- |
| Slug | `return-errors-with-context` |
| Owner | `platform-engineering` |
| Contributor | `codex` |
| Severity | `medium` |

### Rule

Wrap errors.
""",
                encoding="utf-8",
            )

            rules = parse_rules_file(path, "common/go")

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].id, "GO-COM-001")
        self.assertEqual(rules[0].title, "Return errors with context")
        self.assertEqual(rules[0].owner, "platform-engineering")
        self.assertEqual(rules[0].contributor, "codex")

    def test_load_rules_skips_disabled_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            layer = base / "common" / "go"
            layer.mkdir(parents=True)
            (layer / "RULES.md").write_text(
                """# Rules

## GO-COM-001: Enabled rule

| Field | Value |
| --- | --- |
| Owner | `platform-engineering` |

### Rule

Enabled.

## GO-COM-002: Disabled rule

| Field | Value |
| --- | --- |
| Owner | `platform-engineering` |

### Rule

Disabled.
""",
                encoding="utf-8",
            )

            rules = load_rules(base, ("common/go",), frozenset({"GO-COM-002"}))

        self.assertEqual([rule.id for rule in rules], ["GO-COM-001"])


if __name__ == "__main__":
    unittest.main()
