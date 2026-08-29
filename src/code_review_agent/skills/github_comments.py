from __future__ import annotations

from pathlib import Path

from ..github import GitHubContext, GitHubPullRequestCommenter, build_inline_review_comments, build_review_comment


def publish(*, mode: str, output_path: Path, repository_path: Path, comment_mode: str) -> None:
    if comment_mode == "dry_run":
        return

    body = output_path.read_text(encoding="utf-8")
    marker, comment = build_review_comment(mode, output_path, body)
    commenter = GitHubPullRequestCommenter(GitHubContext.from_env())
    result = commenter.publish(marker, comment)
    print(f"GitHub PR comment {result}.")
    if mode == "aggregate":
        return

    inline_comments = build_inline_review_comments(mode, body, repository_path)
    inline_result = commenter.publish_inline_comments(mode, inline_comments)
    print(
        "GitHub inline PR comments "
        f"created/updated: {inline_result.created_or_updated}; stale deleted: {inline_result.stale_deleted}."
    )
