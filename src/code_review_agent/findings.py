from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class ReviewFinding:
    title: str
    severity: str
    path: str | None
    line: int | None
    reasoning: str
    recommendation: str
    rule_id: str = ""
    slug: str = ""
    corrected_code: str = ""
    language: str = "go"


def parse_review_findings(body: str, repository_path: Path) -> tuple[ReviewFinding, ...]:
    structured = parse_json_review_findings(body, repository_path)
    if structured is not None:
        return structured
    return _parse_markdown_findings(body, repository_path)


def parse_json_review_findings(body: str, repository_path: Path) -> tuple[ReviewFinding, ...] | None:
    payload = _json_payload(body)
    if payload is None:
        return None
    raw_findings = payload.get("findings") if isinstance(payload, dict) else payload
    if not isinstance(raw_findings, list):
        return None

    findings: list[ReviewFinding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        finding = _finding_from_mapping(item, repository_path)
        if finding:
            findings.append(finding)
    return tuple(findings)


def render_review_findings_markdown(findings: tuple[ReviewFinding, ...], empty_message: str) -> str:
    if not findings:
        return empty_message

    lines: list[str] = []
    for finding in findings:
        lines.extend(
            [
                f"### {finding.title}",
                "",
            ]
        )
        if finding.rule_id:
            lines.append(f"- Rule ID: `{finding.rule_id}`")
        if finding.slug:
            lines.append(f"- Slug: `{finding.slug}`")
        lines.extend([f"- Severity: `{finding.severity}`", f"- File: `{finding.path}`", f"- Line: {finding.line}"])
        if finding.reasoning:
            lines.append(f"- Reasoning: {finding.reasoning}")
        if finding.recommendation:
            lines.append(f"- Recommendation: {finding.recommendation}")
        lines.append("")
        if finding.corrected_code:
            lines.extend([f"```{finding.language or 'go'}", finding.corrected_code, "```", ""])
    return "\n".join(lines).rstrip()


def _json_payload(body: str) -> Any:
    fenced = re.search(r"```json\s*(?P<payload>.*?)\s*```", body, flags=re.DOTALL | re.IGNORECASE)
    candidate = fenced.group("payload") if fenced else body.strip()
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _finding_from_mapping(item: dict[str, Any], repository_path: Path) -> ReviewFinding | None:
    title = str(item.get("title", "")).strip()
    path = _normalize_path(str(item.get("file") or item.get("path") or ""), repository_path)
    line = _line_number(item.get("line"))
    if not title or not path or not line:
        return None
    return ReviewFinding(
        title=title,
        rule_id=str(item.get("rule_id") or item.get("rule") or "").strip("` "),
        slug=str(item.get("slug") or "").strip("` "),
        severity=_severity(item.get("severity")),
        path=path,
        line=line,
        reasoning=str(item.get("reasoning") or "").strip(),
        recommendation=str(item.get("recommendation") or "").strip(),
        corrected_code=_clean_corrected_code(str(item.get("corrected_code") or item.get("code") or "")),
        language=str(item.get("language") or "go").strip("` ") or "go",
    )


def _severity(value: Any) -> str:
    severity = str(value or "P3").strip("` ").upper()
    return severity if severity in {"P0", "P1", "P2", "P3"} else "P3"


def _clean_corrected_code(value: str) -> str:
    code = value.strip()
    fenced = re.fullmatch(r"```[A-Za-z0-9_-]*\n(?P<code>.*?)\n```", code, flags=re.DOTALL)
    return fenced.group("code").strip() if fenced else code


def _parse_markdown_findings(body: str, repository_path: Path) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    for heading, block in _finding_blocks(body):
        fields = _parse_finding_fields(block)
        title = fields.get("title") or heading
        path = _finding_path(fields, repository_path)
        line = _finding_line(fields)
        if not path or not line:
            continue
        code_language, code = _finding_code(block)
        findings.append(
            ReviewFinding(
                title=title,
                rule_id=fields.get("rule_id") or fields.get("rule", ""),
                slug=fields.get("slug", ""),
                severity=fields.get("severity", "P3"),
                path=path,
                line=line,
                reasoning=fields.get("reasoning", ""),
                recommendation=fields.get("recommendation", ""),
                corrected_code=code,
                language=code_language,
            )
        )
    return tuple(findings)


def _finding_blocks(body: str) -> tuple[tuple[str, str], ...]:
    matches = list(re.finditer(r"^#{2,3}\s+(?P<title>.+?)\s*$", body, flags=re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        title = match.group("title").strip()
        block = body[start:end].strip()
        if _looks_like_finding(title, block):
            blocks.append((title, block))
    return tuple(blocks)


def _looks_like_finding(title: str, block: str) -> bool:
    if title.lower().startswith("finding"):
        return True
    fields = _parse_finding_fields(block)
    return bool((fields.get("file") or fields.get("location")) and fields.get("line"))


def _parse_finding_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^(?:-\s+)?(?:\*\*)?(?P<key>[A-Za-z ]+)(?:\*\*)?:\s*(?:\*\*)?(?P<value>.+?)\s*$", line.strip())
        if not match:
            continue
        key = match.group("key").strip().lower().replace(" ", "_")
        value = match.group("value").strip().strip("`").strip("* ")
        fields[key] = value
    return fields


def _finding_path(fields: dict[str, str], repository_path: Path) -> str | None:
    raw_path = fields.get("file")
    if not raw_path and fields.get("location"):
        raw_path = fields["location"].rsplit(":", 1)[0]
    return _normalize_path(raw_path or "", repository_path)


def _normalize_path(raw_path: str, repository_path: Path) -> str | None:
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
    return _line_number(raw_line)


def _line_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _finding_code(block: str) -> tuple[str, str]:
    match = re.search(r"```(?P<language>[A-Za-z0-9_-]*)\n(?P<code>.*?)\n```", block, flags=re.DOTALL)
    if not match:
        return ("go", "")
    return (match.group("language").strip() or "go", match.group("code").strip())
