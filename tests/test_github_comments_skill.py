from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from code_review_agent.skills import github_comments


class GitHubCommentsSkillTest(unittest.TestCase):
    def test_code_rules_publishes_inline_comments_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            output = repo / "review.md"
            output.write_text(
                """### Missing return
- File: demo/foo.go
- Line: 2
- Rule ID: GO-DEMO-001
""",
                encoding="utf-8",
            )
            commenter = Mock()
            commenter.delete.return_value = False
            commenter.publish_inline_comments.return_value.created_or_updated = 1
            commenter.publish_inline_comments.return_value.stale_deleted = 0

            with patch("code_review_agent.skills.github_comments.GitHubContext.from_env"), patch(
                "code_review_agent.skills.github_comments.GitHubPullRequestCommenter", return_value=commenter
            ):
                github_comments.publish(
                    mode="code-rules",
                    output_path=output,
                    repository_path=repo,
                    comment_mode="pr_comment",
                )

            commenter.publish.assert_not_called()
            commenter.delete.assert_called_once_with("<!-- code-review-agent:code-rules -->")
            commenter.publish_inline_comments.assert_called_once()

    def test_aggregate_publishes_artifact_links_comment_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            output = repo / "aggregate.md"
            output.write_text("# Aggregated Review\n", encoding="utf-8")
            commenter = Mock()
            commenter.delete.return_value = False
            commenter.publish.return_value = "created"

            with patch("code_review_agent.skills.github_comments.GitHubContext.from_env"), patch(
                "code_review_agent.skills.github_comments.GitHubPullRequestCommenter", return_value=commenter
            ):
                github_comments.publish(
                    mode="aggregate",
                    output_path=output,
                    repository_path=repo,
                    comment_mode="pr_comment",
                    artifact_links=("Code Rules Review|https://github.example/actions/runs/1",),
                )

            commenter.publish.assert_called_once()
            commenter.delete.assert_called_once_with("<!-- code-review-agent:aggregate -->")
            marker, body = commenter.publish.call_args.args
            self.assertEqual(marker, "<!-- code-review-agent:artifact-links -->")
            self.assertIn("Code Review Artifacts", body)
            self.assertIn("https://github.example/actions/runs/1", body)
            commenter.publish_inline_comments.assert_not_called()


if __name__ == "__main__":
    unittest.main()
