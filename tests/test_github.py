from pathlib import Path
import json
import unittest
from unittest.mock import patch

from code_review_agent.github import GitHubContext, GitHubPullRequestCommenter, build_review_comment


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


def _context() -> GitHubContext:
    return GitHubContext(
        token="token",
        repository="owner/repo",
        pull_request_number=7,
        api_url="https://api.github.test",
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
