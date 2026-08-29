from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .config import DocumentSet


HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


@dataclass(frozen=True)
class DocumentSummary:
    document_set: DocumentSet
    output_path: Path
    headings: tuple[str, ...]
    missing_paths: tuple[Path, ...]


def affected_document_sets(document_sets: tuple[DocumentSet, ...], changed_files: tuple[Path, ...]) -> tuple[DocumentSet, ...]:
    if not changed_files:
        return document_sets

    affected: list[DocumentSet] = []
    for document_set in document_sets:
        candidates = (document_set.prd_path, document_set.td_path, *document_set.code_paths)
        if any(_is_relative_to(changed_file, candidate) or changed_file == candidate for changed_file in changed_files for candidate in candidates):
            affected.append(document_set)
    return tuple(affected)


def write_document_summary(document_set: DocumentSet, output_dir: Path) -> DocumentSummary:
    summary = build_document_summary(document_set, output_dir)
    summary.output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# PRD/TD Summary - {document_set.name}",
        "",
        "This deterministic dry-run summary is generated from markdown headings. LLM summarization is added by the provider integration.",
        "",
        "## Source Documents",
        "",
        f"- PRD: `{document_set.prd_path}`",
        f"- TD: `{document_set.td_path}`",
        "",
        "## Extracted Headings",
        "",
    ]
    if summary.headings:
        lines.extend(f"- {heading}" for heading in summary.headings)
    else:
        lines.append("- No markdown headings found.")
    if summary.missing_paths:
        lines.extend(["", "## Missing Documents", ""])
        lines.extend(f"- `{path}`" for path in summary.missing_paths)
    lines.append("")

    summary.output_path.write_text("\n".join(lines), encoding="utf-8")
    return summary


def build_document_summary(document_set: DocumentSet, output_dir: Path) -> DocumentSummary:
    output_path = output_dir / f"{document_set.id}-prd-td-summary.md"
    missing_paths = tuple(path for path in (document_set.prd_path, document_set.td_path) if not path.exists())
    headings = _collect_headings(document_set.prd_path) + _collect_headings(document_set.td_path)
    return DocumentSummary(document_set=document_set, output_path=output_path, headings=headings, missing_paths=missing_paths)


def _collect_headings(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            headings.append(f"{'  ' * (level - 1)}{match.group(2)}")
    return tuple(headings)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
