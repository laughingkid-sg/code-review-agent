from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib import error, parse, request


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubContext:
    token: str
    repository: str
    pull_request_number: int
    head_sha: str
    api_url: str = "https://api.github.com"

    @classmethod
    def from_env(cls) -> "GitHubContext":
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").strip().rstrip("/")
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
        number = pull_request.get("number")
        head_sha = (pull_request.get("head") or {}).get("sha", "")
        if not isinstance(number, int):
            raise GitHubError("GitHub event did not include pull_request.number.")
        if not head_sha:
            raise GitHubError("GitHub event did not include pull_request.head.sha.")

        return cls(token=token, repository=repository, pull_request_number=number, head_sha=head_sha, api_url=api_url)


@dataclass(frozen=True)
class InlineReviewComment:
    path: str
    line: int
    marker: str
    body: str


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

    def publish_inline_comments(self, comments: tuple[InlineReviewComment, ...]) -> int:
        valid_lines = self._changed_lines_by_file()
        existing_markers = self._existing_inline_markers()
        published = 0
        for comment in comments:
            if comment.marker in existing_markers:
                continue
            if comment.line not in valid_lines.get(comment.path, set()):
                continue
            self._request(
                "POST",
                self._review_comments_url(),
                {
                    "body": f"{comment.marker}\n\n{comment.body.strip()}\n",
                    "commit_id": self.context.head_sha,
                    "path": comment.path,
                    "line": comment.line,
                    "side": "RIGHT",
                },
            )
            published += 1
        return published

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

    def _existing_inline_markers(self) -> set[str]:
        comments = self._request("GET", self._review_comments_url())
        markers: set[str] = set()
        for comment in comments or []:
            match = re.search(r"<!-- code-review-agent-inline:[^>]+ -->", str(comment.get("body", "")))
            if match:
                markers.add(match.group(0))
        return markers

    def _changed_lines_by_file(self) -> dict[str, set[int]]:
        files = self._request("GET", self._files_url())
        changed: dict[str, set[int]] = {}
        for file_item in files or []:
            filename = str(file_item.get("filename", ""))
            patch = str(file_item.get("patch", ""))
            if filename and patch:
                changed[filename] = _patch_new_lines(patch)
        return changed

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


def build_review_comment(mode: str, output_path: Path, body: str) -> tuple[str, str]:
    title = _mode_title(mode)
    marker = f"<!-- code-review-agent:{mode} -->"
    comment = "\n".join(
        [
            f"## {title}",
            "",
            body.strip(),
            "",
            "---",
            f"Generated by `code-review-agent` from `{output_path}`.",
        ]
    )
    return marker, comment


def build_inline_review_comments(mode: str, body: str, repository_path: Path) -> tuple[InlineReviewComment, ...]:
    comments: list[InlineReviewComment] = []
    for title, block in _finding_blocks(body):
        fields = _parse_finding_fields(block)
        path = _finding_path(fields, repository_path)
        line = _finding_line(fields)
        if not path or not line:
            continue
        comment_body = _inline_body(title, fields)
        marker = _inline_marker(mode, path, line, title)
        comments.append(InlineReviewComment(path=path, line=line, marker=marker, body=comment_body))
    return tuple(_dedupe_inline_comments(comments))


def _mode_title(mode: str) -> str:
    titles = {
        "code-rules": "Code Rules Review",
        "business-rules": "Business Rules Review",
        "aggregate": "Aggregated Code Review",
    }
    return titles.get(mode, "Code Review")


def _finding_blocks(body: str) -> tuple[tuple[str, str], ...]:
    matches = list(re.finditer(r"^###\s+(?P<title>.+?)\s*$", body, flags=re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks.append((match.group("title").strip(), body[start:end].strip()))
    return tuple(blocks)


def _parse_finding_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^-\s+(?:\*\*)?(?P<key>[A-Za-z ]+)(?:\*\*)?:\s*(?P<value>.+?)\s*$", line.strip())
        if not match:
            continue
        key = match.group("key").strip().lower().replace(" ", "_")
        value = match.group("value").strip().strip("`")
        fields[key] = value
    return fields


def _finding_path(fields: dict[str, str], repository_path: Path) -> str | None:
    raw_path = fields.get("file")
    if not raw_path and fields.get("location"):
        raw_path = fields["location"].rsplit(":", 1)[0]
    if not raw_path:
        return None

    path = Path(raw_path.strip("`"))
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(repository_path.resolve()))
        except ValueError:
            return path.name
    return str(path)


def _finding_line(fields: dict[str, str]) -> int | None:
    raw_line = fields.get("line")
    if not raw_line and fields.get("location"):
        raw_line = fields["location"].rsplit(":", 1)[-1]
    if not raw_line:
        return None
    match = re.search(r"\d+", raw_line)
    return int(match.group(0)) if match else None


def _inline_body(title: str, fields: dict[str, str]) -> str:
    lines = [f"**{title}**", ""]
    for label, key in (
        ("Rule", "rule"),
        ("Rule ID", "rule_id"),
        ("Slug", "slug"),
        ("Severity", "severity"),
        ("Reasoning", "reasoning"),
        ("Recommendation", "recommendation"),
    ):
        value = fields.get(key)
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _inline_marker(mode: str, path: str, line: int, title: str) -> str:
    digest = hashlib.sha1(f"{mode}:{path}:{line}:{title}".encode("utf-8")).hexdigest()[:12]
    return f"<!-- code-review-agent-inline:{mode}:{digest} -->"


def _dedupe_inline_comments(comments: list[InlineReviewComment]) -> tuple[InlineReviewComment, ...]:
    seen: set[tuple[str, int, str]] = set()
    deduped: list[InlineReviewComment] = []
    for comment in comments:
        key = (comment.path, comment.line, comment.body)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(comment)
    return tuple(deduped)


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
