from pathlib import Path
import json
import unittest
from unittest.mock import patch

from code_review_agent.github import (
    GitHubContext,
    GitHubPullRequestCommenter,
    build_inline_review_comments,
    build_review_comment,
)


class GitHubCommentTest(unittest.TestCase):
    def test_build_review_comment_adds_stable_marker(self) -> None:
        marker, body = build_review_comment("code-rules", Path(".code-review/review.md"), "# Findings")

        self.assertEqual(marker, "<!-- code-review-agent:code-rules -->")
        self.assertIn("## Code Rules Review", body)
        self.assertIn("# Findings", body)

    def test_publish_creates_comment_when_marker_is_missing(self) -> None:
        calls: list[tuple[str, str, dict | None]] = []
        commenter = GitHubPullRequestCommenter(_context())

        with patch("code_review_agent.github.request.urlopen", side_effect=_fake_urlopen(calls, [[]])):
            result = commenter.publish("<!-- marker -->", "hello")

        self.assertEqual(result, "created")
        self.assertEqual(calls[-1][0], "POST")
        self.assertIn("<!-- marker -->", calls[-1][2]["body"])

    def test_publish_updates_existing_comment_with_marker(self) -> None:
        calls: list[tuple[str, str, dict | None]] = []
        comments = [{"body": "old\n<!-- marker -->", "url": "https://api.github.test/comment/1"}]
        commenter = GitHubPullRequestCommenter(_context())

        with patch("code_review_agent.github.request.urlopen", side_effect=_fake_urlopen(calls, [comments])):
            result = commenter.publish("<!-- marker -->", "new")

        self.assertEqual(result, "updated")
        self.assertEqual(calls[-1][0], "PATCH")
        self.assertEqual(calls[-1][1], "https://api.github.test/comment/1")
        self.assertIn("new", calls[-1][2]["body"])

    def test_build_inline_review_comments_parses_provider_findings(self) -> None:
        body = """# Findings

### Missing return after decode error
- **File**: demo-projects/simple-api/internal/handler/product.go
- **Line**: 115
- **Rule ID**: GO-DEMO-001
- **Slug**: thin-http-handlers
- **Severity**: P1
- **Reasoning**: The handler continues after writing an error response.
- **Recommendation**: Return immediately after the error response.

```go
return
```
"""

        comments = build_inline_review_comments("code-rules", body, Path("/repo"))

        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].path, "demo-projects/simple-api/internal/handler/product.go")
        self.assertEqual(comments[0].line, 115)
        self.assertIn("GO-DEMO-001", comments[0].body)
        self.assertIn("thin-http-handlers", comments[0].body)
        self.assertIn("P1", comments[0].body)
        self.assertIn("### [Missing return after decode error](#thin-http-handlers)", comments[0].body)
        self.assertIn("**Reasoning**", comments[0].body)
        self.assertIn("> The handler continues after writing an error response.", comments[0].body)
        self.assertIn("## Recommendation", comments[0].body)
        self.assertIn("```go\nreturn\n```", comments[0].body)
        self.assertTrue(comments[0].marker.startswith("<!-- code-review-agent-inline:code-rules:"))

    def test_build_inline_review_comments_dedupes_nearby_same_rule(self) -> None:
        body = """### Decode error can continue
- File: demo/handler.go
- Line: 114
- Slug: stop-after-request-binding-failure

### Missing return after decode error
- File: demo/handler.go
- Line: 116
- Slug: stop-after-request-binding-failure
"""

        comments = build_inline_review_comments("code-rules", body, Path("/repo"))

        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0].line, 114)

    def test_publish_inline_comments_updates_existing_and_filters_to_changed_lines(self) -> None:
        calls: list[tuple[str, str, dict | None]] = []
        commenter = GitHubPullRequestCommenter(_context())
        comments = build_inline_review_comments(
            "code-rules",
            """### Existing finding
- File: demo/foo.go
- Line: 2
- Rule ID: GO-DEMO-001

### New finding
- File: demo/foo.go
- Line: 3
- Rule ID: GO-DEMO-002

### Unchanged finding
- File: demo/bar.go
- Line: 10
- Rule ID: GO-DEMO-003
""",
            Path("/repo"),
        )
        existing = [{"body": comments[0].marker, "url": "https://api.github.test/pulls/comments/123"}]
        files = [
            {
                "filename": "demo/foo.go",
                "patch": "@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3",
            }
        ]

        with patch("code_review_agent.github.request.urlopen", side_effect=_fake_urlopen(calls, [files, [], existing, []])):
            count = commenter.publish_inline_comments(comments)

        self.assertEqual(count, 2)
        patch_calls = [call for call in calls if call[0] == "PATCH"]
        post_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(patch_calls), 1)
        self.assertEqual(patch_calls[0][1], "https://api.github.test/pulls/comments/123")
        self.assertIn("[View changed line]", patch_calls[0][2]["body"])
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(post_calls[0][1], "https://api.github.test/repos/owner/repo/pulls/7/comments")
        self.assertIn("[View changed line](https://github.example/owner/repo/blob/abc123/demo/foo.go#L3)", post_calls[0][2]["body"])
        self.assertEqual(post_calls[0][2]["commit_id"], "abc123")
        self.assertEqual(post_calls[0][2]["path"], "demo/foo.go")
        self.assertEqual(post_calls[0][2]["line"], 3)
        self.assertEqual(post_calls[0][2]["side"], "RIGHT")


def _context() -> GitHubContext:
    return GitHubContext(
        token="token",
        repository="owner/repo",
        pull_request_number=7,
        head_sha="abc123",
        api_url="https://api.github.test",
        server_url="https://github.example",
    )


def _fake_urlopen(calls: list[tuple[str, str, dict | None]], responses: list[object]):
    def fake_urlopen(req, timeout: int):
        payload = json.loads(req.data.decode("utf-8")) if req.data else None
        calls.append((req.get_method(), req.full_url, payload))
        if req.get_method() == "GET":
            return _Response(responses.pop(0))
        return _Response({"ok": True})

    return fake_urlopen


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
