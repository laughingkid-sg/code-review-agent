from __future__ import annotations

from pathlib import Path

from ..audit import AuditRecorder
from ..config import ReviewConfig
from ..providers import OpenAICompatibleProvider
from ..review import run_code_rules
from ..rules import Rule
from ..skill_prompts import EMPTY_SKILL_PROMPTS, SkillPromptBundle


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
    skill_prompts: SkillPromptBundle = EMPTY_SKILL_PROMPTS,
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
        skill_prompts=skill_prompts,
    )
