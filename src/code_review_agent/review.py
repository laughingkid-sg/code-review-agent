from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

from .audit import AuditRecorder
from .config import DocumentSet, ReviewConfig
from .documents import DocumentSummary, affected_document_sets, build_document_summary, write_document_summary
from .providers import ChatMessage, OpenAICompatibleProvider
from .rules import Rule, compact_review_payload


@dataclass(frozen=True)
class Finding:
    title: str
    rule_id: str
    rule_slug: str
    severity: str
    path: Path | None
    line: int | None
    reasoning: str
    recommendation: str


def run_code_rules(
    config: ReviewConfig,
    rules: tuple[Rule, ...],
    repository_path: Path,
    changed_files: tuple[Path, ...],
    output_path: Path,
    default_contributor: str,
    provider: OpenAICompatibleProvider | None = None,
    audit_recorder: AuditRecorder | None = None,
) -> None:
    files = _review_files(config, repository_path, changed_files)
    findings = _heuristic_findings(rules, files)
    provider_review = _provider_code_review(config, rules, repository_path, files, provider, audit_recorder)
    lines = [
        "# Code Rules Review",
        "",
        f"Mode: {_review_mode(provider)}",
        "",
        "## Loaded Rules",
        "",
    ]
    if rules:
        lines.extend(
            f"- `{rule.id}` `{rule.slug}` {rule.title} ({rule.layer}; severity: {rule.severity}; contributor: {rule.contributor or default_contributor})"
            for rule in rules
        )
    else:
        lines.append("- No rules loaded.")

    lines.extend(["", "## Reviewed Files", ""])
    if files:
        lines.extend(f"- `{path}`" for path in files)
    else:
        lines.append("- No Go files selected for review.")

    if provider_review:
        lines.extend(["", "## Provider Review", "", provider_review, ""])

    lines.extend(["", "## Findings", ""])
    if findings:
        for finding in findings:
            location = f"{finding.path}:{finding.line}" if finding.path and finding.line else "repository"
            lines.extend(
                [
                    f"### {finding.title}",
                    "",
                    f"- Rule: `{finding.rule_id}`",
                    f"- Slug: `{finding.rule_slug}`",
                    f"- Severity: `{finding.severity}`",
                    f"- Location: `{location}`",
                    f"- Reasoning: {finding.reasoning}",
                    f"- Recommendation: {finding.recommendation}",
                    "",
                ]
            )
    else:
        lines.append("- No deterministic heuristic findings.")

    _write_output(output_path, lines)


def run_business_rules(
    config: ReviewConfig,
    changed_files: tuple[Path, ...],
    output_path: Path,
    provider: OpenAICompatibleProvider | None = None,
    audit_recorder: AuditRecorder | None = None,
    summary_cache_ttl_days: int = 3,
) -> None:
    document_sets = affected_document_sets(config.document_sets, changed_files)
    summaries = tuple(
        _prepare_summary(document_set, config, provider, audit_recorder, summary_cache_ttl_days)
        for document_set in document_sets
    )
    provider_reviews: list[str] = []
    if provider:
        for summary in summaries:
            provider_reviews.append(_provider_business_review(config, summary, changed_files, provider, audit_recorder))
    lines = [
        "# Business Rules Review",
        "",
        f"Mode: {_review_mode(provider)}",
        "",
        "This run generates PR-specific PRD/TD summary artifacts and checks implementation logic against those artifacts.",
        "",
        "## Affected Document Sets",
        "",
    ]
    if summaries:
        for summary in summaries:
            lines.extend(_summary_lines(summary))
    else:
        lines.append("- No affected document sets detected.")
    if provider_reviews:
        lines.extend(["", "## Provider Review", ""])
        for provider_review in provider_reviews:
            lines.extend([provider_review, ""])
    _write_output(output_path, lines)


def _prepare_summary(
    document_set: DocumentSet,
    config: ReviewConfig,
    provider: OpenAICompatibleProvider | None,
    audit_recorder: AuditRecorder | None,
    summary_cache_ttl_days: int,
) -> DocumentSummary:
    if not provider:
        return write_document_summary(document_set, config.summary_artifact_dir)

    summary = build_document_summary(document_set, config.summary_artifact_dir)
    if _cached_summary_is_fresh(summary, summary_cache_ttl_days):
        return summary

    provider_summary = _provider_document_summary(summary, provider, audit_recorder)
    summary.output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.output_path.write_text(provider_summary, encoding="utf-8")
    return summary


def _cached_summary_is_fresh(summary: DocumentSummary, ttl_days: int) -> bool:
    if ttl_days <= 0 or not summary.output_path.exists():
        return False

    summary_mtime = summary.output_path.stat().st_mtime
    if time.time() - summary_mtime > ttl_days * 24 * 60 * 60:
        return False

    source_paths = (summary.document_set.prd_path, summary.document_set.td_path)
    return all(not path.exists() or path.stat().st_mtime <= summary_mtime for path in source_paths)


def run_aggregate(output_path: Path) -> None:
    _write_output(
        output_path,
        [
            "# Aggregated Review",
            "",
            "Mode: deterministic dry-run",
            "",
            "Aggregation is reserved for combining code-rules and business-rules artifacts after both jobs complete.",
            "",
        ],
    )


def _review_files(config: ReviewConfig, repository_path: Path, changed_files: tuple[Path, ...]) -> tuple[Path, ...]:
    if changed_files:
        return tuple(path for path in changed_files if path.suffix == ".go" and path.exists())

    files: list[Path] = []
    for document_set in config.document_sets:
        for code_path in document_set.code_paths:
            if code_path.exists():
                files.extend(sorted(code_path.rglob("*.go")))
    return tuple(files)


def _provider_code_review(
    config: ReviewConfig,
    rules: tuple[Rule, ...],
    repository_path: Path,
    files: tuple[Path, ...],
    provider: OpenAICompatibleProvider | None,
    audit_recorder: AuditRecorder | None,
) -> str:
    if not provider:
        return ""
    if not rules:
        return "No rules were loaded, so provider-backed code-rule review was skipped."
    if not files:
        return "No Go files were selected, so provider-backed code-rule review was skipped."

    messages = [
        ChatMessage(role="system", content="You are a concise CI code review agent. Return markdown only."),
        ChatMessage(
            role="user",
            content="\n\n".join(
                [
                    f"Repository: {config.repository_name}",
                    "Review only the provided Go files against the rules below. Flag only issues directly supported by the code.",
                    (
                        "For each finding, include title, rule ID, slug, severity, file, line, reasoning, "
                        "recommendation, and a minimal corrected code snippet in a fenced go block. "
                        "If there are no findings, say so."
                    ),
                    "# Rules",
                    compact_review_payload(rules),
                    "# Changed Go Files",
                    _code_context(repository_path, files),
                ]
            ),
        ),
    ]
    result = provider.chat(messages, max_tokens=1400, temperature=0)
    if audit_recorder:
        audit_recorder.write("code-rules-review", messages, result)
    return result.content


def _provider_document_summary(
    summary: DocumentSummary,
    provider: OpenAICompatibleProvider,
    audit_recorder: AuditRecorder | None,
) -> str:
    document_set = summary.document_set
    messages = [
        ChatMessage(role="system", content="You summarize PRD/TD documents for code review. Return markdown only."),
        ChatMessage(
            role="user",
            content="\n\n".join(
                [
                    f"Document set: {document_set.name}",
                    "Summarize the PRD and TD for a CI business-logic review artifact.",
                    "Return concise markdown with: Goals, Functional Requirements, Technical Constraints, Review Focus, and Open Questions.",
                    "# PRD",
                    _read_text_budget(document_set.prd_path, 9000),
                    "# TD",
                    _read_text_budget(document_set.td_path, 9000),
                ]
            ),
        ),
    ]
    result = provider.chat(messages, max_tokens=1400, temperature=0)
    if audit_recorder:
        audit_recorder.write(f"business-summary-{document_set.id}", messages, result)
    return f"# PRD/TD Summary - {document_set.name}\n\n{result.content.strip()}\n"


def _provider_business_review(
    config: ReviewConfig,
    summary: DocumentSummary,
    changed_files: tuple[Path, ...],
    provider: OpenAICompatibleProvider,
    audit_recorder: AuditRecorder | None,
) -> str:
    document_set = summary.document_set
    files = _business_review_files(document_set.code_paths, changed_files)
    if not files:
        return f"### {document_set.name}\n\nNo implementation files were selected for provider-backed business review."

    messages = [
        ChatMessage(role="system", content="You are a concise business-logic code review agent. Return markdown only."),
        ChatMessage(
            role="user",
            content="\n\n".join(
                [
                    f"Repository: {config.repository_name}",
                    f"Document set: {document_set.name}",
                    "Review the implementation against the PRD/TD summary. Focus on changed files, but use the supporting files to avoid false positives.",
                    f"Changed files: {_changed_file_list(changed_files)}",
                    "Flag business logic mismatches, missing required behavior, and incorrect conditions. Do not flag a requirement as missing when a supporting file implements it.",
                    (
                        "For each finding, include title, severity P0-P3, file, line, reasoning, "
                        "recommendation, and a minimal corrected code snippet in a fenced go block when a code change is clear. "
                        "If there are no findings, say so."
                    ),
                    "# PRD/TD Summary",
                    summary.output_path.read_text(encoding="utf-8"),
                    "# Implementation Files",
                    _code_context(_common_parent(document_set.code_paths), files),
                ]
            ),
        ),
    ]
    result = provider.chat(messages, max_tokens=1400, temperature=0)
    if audit_recorder:
        audit_recorder.write(f"business-review-{document_set.id}", messages, result)
    return f"### {document_set.name}\n\n{result.content.strip()}"


def _business_review_files(code_paths: tuple[Path, ...], changed_files: tuple[Path, ...]) -> tuple[Path, ...]:
    files: list[Path] = []
    if changed_files:
        files.extend(path for path in changed_files if path.suffix == ".go" and path.exists())

    for code_path in code_paths:
        if code_path.exists():
            files.extend(path for path in sorted(code_path.rglob("*.go")) if not path.name.endswith("_test.go"))
    return tuple(dict.fromkeys(files))


def _changed_file_list(changed_files: tuple[Path, ...]) -> str:
    files = [str(path) for path in changed_files]
    if not files:
        return "all files in affected document set"
    return ", ".join(files)


def _code_context(repository_path: Path, files: tuple[Path, ...], max_chars: int = 20000) -> str:
    chunks: list[str] = []
    remaining = max_chars
    for path in files:
        if remaining <= 0:
            break
        rel_path = _relative_path(path, repository_path)
        numbered = _numbered_lines(path)
        chunk = f"## {rel_path}\n\n```go\n{numbered}\n```"
        if len(chunk) > remaining:
            chunk = chunk[:remaining] + "\n...[truncated]"
        chunks.append(chunk)
        remaining -= len(chunk)
    return "\n\n".join(chunks)


def _numbered_lines(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))


def _read_text_budget(path: Path, max_chars: int) -> str:
    if not path.exists():
        return f"Missing document: {path}"
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _relative_path(path: Path, repository_path: Path) -> str:
    try:
        return str(path.relative_to(repository_path))
    except ValueError:
        return str(path)


def _common_parent(paths: tuple[Path, ...]) -> Path:
    if not paths:
        return Path(".")
    return paths[0].parent


def _review_mode(provider: OpenAICompatibleProvider | None) -> str:
    return "provider-backed qwen review" if provider else "deterministic dry-run"


def _heuristic_findings(rules: tuple[Rule, ...], files: tuple[Path, ...]) -> tuple[Finding, ...]:
    rule_map = {rule.id: rule for rule in rules}
    findings: list[Finding] = []
    decode_rule = rule_map.get("GO-DEMO-PROJ-001")
    if decode_rule:
        findings.extend(_request_decode_findings(decode_rule, files))
    error_rule = rule_map.get("GO-COM-001")
    if error_rule:
        findings.extend(_generic_error_findings(error_rule, files))
    return tuple(findings)


def _request_decode_findings(rule: Rule, files: tuple[Path, ...]) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    pattern = re.compile(r"if\s+err\s*:=\s*(?:.*Decode|.*ShouldBindJSON|.*Atoi|.*Parse).+err\s*!=")
    for path in files:
        if path.name.endswith("_test.go"):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not pattern.search(line):
                continue
            window = lines[index + 1 : index + 7]
            block_end = next((offset for offset, value in enumerate(window, start=1) if value.strip() == "}"), None)
            inspected = window[:block_end] if block_end else window
            if inspected and not any(value.strip() == "return" for value in inspected):
                findings.append(
                    Finding(
                        title="Handler continues after request parsing failure",
                        rule_id=rule.id,
                        rule_slug=rule.slug,
                        severity=rule.severity,
                        path=path,
                        line=index + 1,
                        reasoning="The handler detects an invalid request but the nearby error branch does not return before execution can continue.",
                        recommendation="Return immediately after writing the bad-request or validation error response.",
                    )
                )
    return tuple(findings)


def _generic_error_findings(rule: Rule, files: tuple[Path, ...]) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    pattern = re.compile(r"errors\.New\(\"(?:failed|error|invalid)\"\)")
    for path in files:
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                findings.append(
                    Finding(
                        title="Generic error message loses context",
                        rule_id=rule.id,
                        rule_slug=rule.slug,
                        severity=rule.severity,
                        path=path,
                        line=index,
                        reasoning="A generic error string makes it harder to identify the failed operation during review or incident debugging.",
                        recommendation="Wrap the original error or include operation-specific context in the error message.",
                    )
                )
    return tuple(findings)


def _summary_lines(summary: DocumentSummary) -> list[str]:
    lines = [
        f"### {summary.document_set.name}",
        "",
        f"- Summary artifact: `{summary.output_path}`",
        f"- Extracted headings: {len(summary.headings)}",
    ]
    if summary.missing_paths:
        lines.append(f"- Missing documents: {len(summary.missing_paths)}")
    lines.append("")
    return lines


def _write_output(output_path: Path, lines: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
