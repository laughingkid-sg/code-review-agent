from __future__ import annotations

from pathlib import Path

from ..github import GitHubContext, GitHubPullRequestCommenter, build_artifact_links_comment, build_inline_review_comments


def publish(
    *,
    mode: str,
    output_path: Path,
    repository_path: Path,
    comment_mode: str,
    artifact_links: tuple[str, ...] = (),
) -> None:
    if comment_mode == "dry_run":
        return

    body = output_path.read_text(encoding="utf-8")
    commenter = GitHubPullRequestCommenter(GitHubContext.from_env())
    legacy_deleted = commenter.delete(f"<!-- code-review-agent:{mode} -->")
    if legacy_deleted:
        print(f"Legacy GitHub PR summary comment deleted for {mode}.")
    if mode == "aggregate":
        marker, comment = build_artifact_links_comment(artifact_links)
        result = commenter.publish(marker, comment)
        print(f"GitHub artifact links PR comment {result}.")
        return

    inline_comments = build_inline_review_comments(mode, body, repository_path)
    inline_result = commenter.publish_inline_comments(mode, inline_comments)
    print(
        "GitHub inline PR comments "
        f"created/updated: {inline_result.created_or_updated}; stale deleted: {inline_result.stale_deleted}."
    )
