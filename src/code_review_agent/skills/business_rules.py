from __future__ import annotations

from pathlib import Path

from ..audit import AuditRecorder
from ..config import ReviewConfig
from ..providers import OpenAICompatibleProvider
from ..review import run_business_rules
from ..skill_prompts import EMPTY_SKILL_PROMPTS, SkillPromptBundle


def run(
    *,
    config: ReviewConfig,
    repository_path: Path,
    changed_files: tuple[Path, ...],
    output_path: Path,
    provider: OpenAICompatibleProvider | None,
    audit_recorder: AuditRecorder | None,
    summary_cache_ttl_days: int,
    skill_prompts: SkillPromptBundle = EMPTY_SKILL_PROMPTS,
) -> None:
    run_business_rules(
        config=config,
        repository_path=repository_path,
        changed_files=changed_files,
        output_path=output_path,
        provider=provider,
        audit_recorder=audit_recorder,
        summary_cache_ttl_days=summary_cache_ttl_days,
        skill_prompts=skill_prompts,
    )
