from pathlib import Path
import unittest

from code_review_agent.findings import parse_review_findings


class FindingParsingTest(unittest.TestCase):
    def test_parse_markdown_findings(self) -> None:
        findings = parse_review_findings(
            """### Missing return
- File: demo/handler.go
- Line: 12
- Rule ID: GO-DEMO-001
- Slug: stop-after-request-binding-failure
- Severity: P1
- Reasoning: The handler keeps running.
- Recommendation: Return after writing the error.

```go
return
```
""",
            Path("/repo"),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].title, "Missing return")
        self.assertEqual(findings[0].rule_id, "GO-DEMO-001")
        self.assertEqual(findings[0].slug, "stop-after-request-binding-failure")
        self.assertEqual(findings[0].path, "demo/handler.go")
        self.assertEqual(findings[0].line, 12)
        self.assertEqual(findings[0].corrected_code, "return")

    def test_parse_json_findings(self) -> None:
        findings = parse_review_findings(
            """```json
[
  {
    "title": "Negative price accepted",
    "rule_id": "GO-DEMO-PROJ-002",
    "slug": "reject-negative-monetary-amounts",
    "severity": "P1",
    "file": "/repo/demo/model.go",
    "line": 62,
    "reasoning": "Price check is too relaxed.",
    "recommendation": "Reject values below zero.",
    "corrected_code": "if r.Price < 0 {\\n\\treturn err\\n}"
  }
]
```""",
            Path("/repo"),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path, "demo/model.go")
        self.assertEqual(findings[0].line, 62)
        self.assertIn("r.Price < 0", findings[0].corrected_code)

    def test_parse_provider_heading_findings(self) -> None:
        findings = parse_review_findings(
            """## Finding 1
**Title:** Handler continues execution after JSON decode failure
**Rule ID:** GO-DEMO-PROJ-001
**Slug:** stop-after-request-binding-failure
**Severity:** P1
**File:** demo/handler.go
**Line:** 116
**Reasoning:** Decode errors fall through.
**Recommendation:** Return after writeError.

```go
return
```
""",
            Path("/repo"),
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].title, "Handler continues execution after JSON decode failure")
        self.assertEqual(findings[0].rule_id, "GO-DEMO-PROJ-001")
        self.assertEqual(findings[0].slug, "stop-after-request-binding-failure")
        self.assertEqual(findings[0].line, 116)
        self.assertEqual(findings[0].corrected_code, "return")


if __name__ == "__main__":
    unittest.main()
