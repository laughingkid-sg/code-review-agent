from __future__ import annotations

from pathlib import Path

from ..audit import AuditRecorder
from ..config import ReviewConfig
from ..providers import OpenAICompatibleProvider
from ..review import run_code_rules
from ..rules import Rule


def run(
    *,
    config: ReviewConfig,
    rules: tuple[Rule, ...],
    repository_path: Path,
    changed_files: tuple[Path, ...],
    output_path: Path,
    default_contributor: str,
    provider: OpenAICompatibleProvider | None,
    audit_recorder: AuditRecorder | None,
) -> None:
    run_code_rules(
        config=config,
        rules=rules,
        repository_path=repository_path,
        changed_files=changed_files,
        output_path=output_path,
        default_contributor=default_contributor,
        provider=provider,
        audit_recorder=audit_recorder,
    )
