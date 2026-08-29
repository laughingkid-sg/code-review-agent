from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import ReviewConfig
from .documents import DocumentSummary, affected_document_sets, write_document_summary
from .rules import Rule


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
) -> None:
    files = _review_files(config, repository_path, changed_files)
    findings = _heuristic_findings(rules, files)
    lines = [
        "# Code Rules Review",
        "",
        "Mode: deterministic dry-run",
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


def run_business_rules(config: ReviewConfig, changed_files: tuple[Path, ...], output_path: Path) -> None:
    document_sets = affected_document_sets(config.document_sets, changed_files)
    summaries = tuple(write_document_summary(document_set, config.summary_artifact_dir) for document_set in document_sets)
    lines = [
        "# Business Rules Review",
        "",
        "Mode: deterministic dry-run",
        "",
        "This run generates PR-specific PRD/TD summary artifacts. Requirement-to-code reasoning is added by the provider integration.",
        "",
        "## Affected Document Sets",
        "",
    ]
    if summaries:
        for summary in summaries:
            lines.extend(_summary_lines(summary))
    else:
        lines.append("- No affected document sets detected.")
    _write_output(output_path, lines)


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
