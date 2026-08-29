from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib import error, parse, request

from .findings import ReviewFinding, parse_review_findings


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubContext:
    token: str
    repository: str
    pull_request_number: int
    head_sha: str
    api_url: str = "https://api.github.com"
    server_url: str = "https://github.com"

    @classmethod
    def from_env(cls) -> "GitHubContext":
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").strip().rstrip("/")
        server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
        missing = [
            name
            for name, value in (
                ("GITHUB_TOKEN", token),
                ("GITHUB_REPOSITORY", repository),
                ("GITHUB_EVENT_PATH", event_path),
            )
            if not value
        ]
        if missing:
            raise GitHubError(f"Missing required environment variable(s): {', '.join(missing)}")

        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pull_request = event.get("pull_request") or {}
        number = _int_or_none(os.environ.get("CODE_REVIEW_PR_NUMBER")) or pull_request.get("number")
        head_sha = os.environ.get("CODE_REVIEW_HEAD_SHA", "").strip() or (pull_request.get("head") or {}).get("sha", "")
        if not isinstance(number, int):
            raise GitHubError("GitHub event did not include pull_request.number.")
        if not head_sha:
            raise GitHubError("GitHub event did not include pull_request.head.sha.")

        return cls(
            token=token,
            repository=repository,
            pull_request_number=number,
            head_sha=head_sha,
            api_url=api_url,
            server_url=server_url,
        )


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class InlineReviewComment:
    path: str
    line: int
    marker: str
    body: str


@dataclass(frozen=True)
class InlinePublishResult:
    created_or_updated: int
    stale_deleted: int


@dataclass(frozen=True)
class GitHubPullRequestCommenter:
    context: GitHubContext

    def publish(self, marker: str, body: str) -> str:
        existing = self._find_existing_comment(marker)
        comment_body = f"{marker}\n\n{body.strip()}\n"
        if existing:
            self._request("PATCH", existing["url"], {"body": comment_body})
            return "updated"
        self._request("POST", self._comments_url(), {"body": comment_body})
        return "created"

    def delete(self, marker: str) -> bool:
        existing = self._find_existing_comment(marker)
        if not existing:
            return False
        self._request("DELETE", existing["url"])
        return True

    def publish_inline_comments(self, mode: str, comments: tuple[InlineReviewComment, ...]) -> InlinePublishResult:
        valid_lines = self._changed_lines_by_file()
        existing_comments = self._existing_inline_comments(mode)
        desired_markers = {comment.marker for comment in comments}
        created_or_updated = 0
        stale_deleted = 0
        for comment in comments:
            if comment.line not in valid_lines.get(comment.path, set()):
                continue
            comment_body = self._format_inline_comment(comment)
            existing = existing_comments.get(comment.marker)
            if existing:
                self._request("PATCH", existing["url"], {"body": comment_body})
                created_or_updated += 1
                continue
            self._request(
                "POST",
                self._review_comments_url(),
                {
                    "body": comment_body,
                    "commit_id": self.context.head_sha,
                    "path": comment.path,
                    "line": comment.line,
                    "side": "RIGHT",
                },
            )
            created_or_updated += 1

        for marker, existing in existing_comments.items():
            if marker not in desired_markers:
                self._request("DELETE", existing["url"])
                stale_deleted += 1
        return InlinePublishResult(created_or_updated=created_or_updated, stale_deleted=stale_deleted)

    def _find_existing_comment(self, marker: str) -> dict[str, Any] | None:
        page = 1
        while True:
            url = f"{self._comments_url()}?{parse.urlencode({'per_page': 100, 'page': page})}"
            comments = self._request("GET", url)
            if not comments:
                return None
            for comment in comments:
                if marker in str(comment.get("body", "")):
                    return comment
            page += 1

    def _comments_url(self) -> str:
        return f"{self.context.api_url}/repos/{self.context.repository}/issues/{self.context.pull_request_number}/comments"

    def _review_comments_url(self) -> str:
        return f"{self.context.api_url}/repos/{self.context.repository}/pulls/{self.context.pull_request_number}/comments"

    def _files_url(self) -> str:
        return f"{self.context.api_url}/repos/{self.context.repository}/pulls/{self.context.pull_request_number}/files"

    def _existing_inline_comments(self, mode: str) -> dict[str, dict[str, Any]]:
        page = 1
        comments_by_marker: dict[str, dict[str, Any]] = {}
        marker_re = re.compile(rf"<!-- code-review-agent-inline:{re.escape(mode)}:[^>]+ -->")
        while True:
            url = f"{self._review_comments_url()}?{parse.urlencode({'per_page': 100, 'page': page})}"
            comments = self._request("GET", url)
            if not comments:
                return comments_by_marker
            for comment in comments:
                match = marker_re.search(str(comment.get("body", "")))
                if match:
                    comments_by_marker[match.group(0)] = comment
            page += 1

    def _changed_lines_by_file(self) -> dict[str, set[int]]:
        changed: dict[str, set[int]] = {}
        page = 1
        while True:
            url = f"{self._files_url()}?{parse.urlencode({'per_page': 100, 'page': page})}"
            files = self._request("GET", url)
            if not files:
                return changed
            for file_item in files:
                filename = str(file_item.get("filename", ""))
                patch = str(file_item.get("patch", ""))
                if filename and patch:
                    changed[filename] = _patch_new_lines(patch)
            page += 1

    def _format_inline_comment(self, comment: InlineReviewComment) -> str:
        return "\n".join(
            [
                comment.marker,
                "",
                comment.body.strip(),
                "",
                "---",
                f"[View changed line]({self._line_url(comment)})",
                "",
            ]
        )

    def _line_url(self, comment: InlineReviewComment) -> str:
        path = parse.quote(comment.path, safe="/")
        return f"{self.context.server_url}/{self.context.repository}/blob/{self.context.head_sha}/{path}#L{comment.line}"

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            url=url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.context.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else None
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"GitHub HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise GitHubError(f"GitHub request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise GitHubError("GitHub response was not valid JSON.") from exc


def build_artifact_links_comment(artifact_links: tuple[str, ...]) -> tuple[str, str]:
    marker = "<!-- code-review-agent:artifact-links -->"
    rows = [_artifact_link_row(value) for value in artifact_links]
    rows = [row for row in rows if row]
    lines = [
        "## Code Review Artifacts",
        "",
        "Exact-line review findings are posted on the changed code. Full review reasoning and LLM transcripts are kept in CI artifacts for debugging.",
        "",
    ]
    if rows:
        lines.extend(["| Artifact | Link |", "| --- | --- |", *rows])
    else:
        lines.append("Artifacts are available from the completed GitHub Actions review runs for this PR.")
    return marker, "\n".join(lines)


def _artifact_link_row(value: str) -> str:
    label, separator, url = value.partition("|")
    if not separator:
        return ""
    label = label.strip()
    url = url.strip()
    if not label or not url:
        return ""
    return f"| {label} | [Open]({url}) |"


def build_inline_review_comments(mode: str, body: str, repository_path: Path) -> tuple[InlineReviewComment, ...]:
    comments: list[InlineReviewComment] = []
    for finding in parse_review_findings(body, repository_path):
        if not finding.path or not finding.line:
            continue
        comment_body = _inline_body(finding)
        marker = _inline_marker(mode, finding.path, finding.line, finding.title)
        comments.append(InlineReviewComment(path=finding.path, line=finding.line, marker=marker, body=comment_body))
    return tuple(_dedupe_inline_comments(comments))


def _inline_body(finding: ReviewFinding) -> str:
    title_line = f"### [{finding.title}](#{finding.slug})" if finding.slug else f"### {finding.title}"
    lines = [title_line, ""]

    if finding.rule_id:
        lines.extend([f"**RuleID:** `{_strip_code_ticks(finding.rule_id)}`", ""])

    if finding.severity:
        lines.extend([f"**Severity:** `{_strip_code_ticks(finding.severity)}`", ""])

    if finding.reasoning:
        lines.extend(["**Reasoning**", f"> {_strip_code_ticks(finding.reasoning)}", ""])

    if finding.recommendation:
        lines.extend(["## Recommendation", _strip_code_ticks(finding.recommendation), ""])

    if finding.corrected_code:
        language = finding.language or "go"
        lines.extend([f"```{language}\n{finding.corrected_code}\n```", ""])

    return "\n".join(lines)


def _strip_code_ticks(value: str) -> str:
    return value.strip().strip("`")


def _inline_marker(mode: str, path: str, line: int, title: str) -> str:
    digest = hashlib.sha1(f"{mode}:{path}:{line}:{title}".encode("utf-8")).hexdigest()[:12]
    return f"<!-- code-review-agent-inline:{mode}:{digest} -->"


def _dedupe_inline_comments(comments: list[InlineReviewComment]) -> tuple[InlineReviewComment, ...]:
    seen: set[tuple[str, int, str]] = set()
    nearby_rule_lines: dict[tuple[str, str], list[int]] = {}
    deduped: list[InlineReviewComment] = []
    for comment in comments:
        key = (comment.path, comment.line, comment.body)
        if key in seen:
            continue
        rule_key = _inline_rule_key(comment)
        if rule_key:
            nearby_lines = nearby_rule_lines.setdefault(rule_key, [])
            if any(abs(comment.line - line) <= 5 for line in nearby_lines):
                continue
            nearby_lines.append(comment.line)
        seen.add(key)
        deduped.append(comment)
    return tuple(deduped)


def _inline_rule_key(comment: InlineReviewComment) -> tuple[str, str] | None:
    title_slug = re.search(r"^###\s+\[.+?\]\(#(?P<slug>[a-z0-9][a-z0-9-]*)\)", comment.body, flags=re.MULTILINE)
    if title_slug:
        return (comment.path, title_slug.group("slug"))
    rule_id = re.search(r"^\*\*RuleID:\*\*\s+`?(?P<value>[^`\n]+)`?\s*$", comment.body, flags=re.MULTILINE)
    if rule_id:
        return (comment.path, rule_id.group("value").strip().lower())
    return None


def _patch_new_lines(patch: str) -> set[int]:
    lines: set[int] = set()
    new_line = 0
    for raw_line in patch.splitlines():
        hunk = re.match(r"^@@\s+-\d+(?:,\d+)?\s+\+(?P<start>\d+)(?:,\d+)?\s+@@", raw_line)
        if hunk:
            new_line = int(hunk.group("start"))
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            lines.add(new_line)
            new_line += 1
        elif raw_line.startswith(" "):
            lines.add(new_line)
            new_line += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            continue
    return lines
