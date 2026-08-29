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

## [Return errors with context](#return-errors-with-context)

| Field | Value |
| --- | --- |
| ID | `GO-COM-001` |
| Slug | `return-errors-with-context` |
| Contributor | `example@gmail.com` |
| Severity | `P2` |
| Tags | `errors`, `observability` |
| References | None |

### Rule

Wrap errors.
""",
                encoding="utf-8",
            )

            rules = parse_rules_file(path, "common/go")

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].id, "GO-COM-001")
        self.assertEqual(rules[0].slug, "return-errors-with-context")
        self.assertEqual(rules[0].title, "Return errors with context")
        self.assertEqual(rules[0].contributor, "example@gmail.com")
        self.assertEqual(rules[0].severity, "P2")

    def test_compact_review_payload_excludes_governance_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "RULES.md"
            path.write_text(
                """# Rules

## [Return errors with context](#return-errors-with-context)

| Field | Value |
| --- | --- |
| ID | `GO-COM-001` |
| Slug | `return-errors-with-context` |
| Contributor | `example@gmail.com` |
| Severity | `P2` |
| Tags | `errors`, `observability` |
| References | None |

### Rule

Wrap errors.

### Review Checklist

- Check returned errors.
""",
                encoding="utf-8",
            )

            payload = parse_rules_file(path, "common/go")[0].compact_review_payload()

        self.assertIn("ID: GO-COM-001", payload)
        self.assertIn("Severity: P2", payload)
        self.assertIn("## return-errors-with-context", payload)
        self.assertIn("Wrap errors.", payload)
        self.assertNotIn("Contributor", payload)
        self.assertNotIn("example@gmail.com", payload)
        self.assertNotIn("Tags", payload)
        self.assertNotIn("References", payload)

    def test_load_rules_skips_disabled_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            layer = base / "common" / "go"
            layer.mkdir(parents=True)
            (layer / "RULES.md").write_text(
                """# Rules

## [Enabled rule](#enabled-rule)

| Field | Value |
| --- | --- |
| ID | `GO-COM-001` |
| Slug | `enabled-rule` |
| Severity | `P2` |

### Rule

Enabled.

## [Disabled rule](#disabled-rule)

| Field | Value |
| --- | --- |
| ID | `GO-COM-002` |
| Slug | `disabled-rule` |
| Severity | `P2` |

### Rule

Disabled.
""",
                encoding="utf-8",
            )

            rules = load_rules(base, ("common/go",), frozenset({"GO-COM-002"}))

        self.assertEqual([rule.id for rule in rules], ["GO-COM-001"])


if __name__ == "__main__":
    unittest.main()
