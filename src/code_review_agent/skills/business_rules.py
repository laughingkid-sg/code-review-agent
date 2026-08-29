from __future__ import annotations

from pathlib import Path

from ..audit import AuditRecorder
from ..config import ReviewConfig
from ..providers import OpenAICompatibleProvider
from ..review import run_business_rules


def run(
    *,
    config: ReviewConfig,
    changed_files: tuple[Path, ...],
    output_path: Path,
    provider: OpenAICompatibleProvider | None,
    audit_recorder: AuditRecorder | None,
    summary_cache_ttl_days: int,
) -> None:
    run_business_rules(
        config=config,
        changed_files=changed_files,
        output_path=output_path,
        provider=provider,
        audit_recorder=audit_recorder,
        summary_cache_ttl_days=summary_cache_ttl_days,
    )
