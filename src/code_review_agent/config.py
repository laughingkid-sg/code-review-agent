from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DocumentSet:
    id: str
    name: str
    prd_path: Path
    td_path: Path
    code_paths: tuple[Path, ...]


@dataclass(frozen=True)
class ReviewConfig:
    repository_name: str
    department: str
    project: str
    languages: tuple[str, ...]
    enabled_skills: tuple[str, ...]
    knowledge_layers: tuple[str, ...]
    disabled_rules: frozenset[str]
    summary_artifact_dir: Path
    document_sets: tuple[DocumentSet, ...]
    code_rules_output: Path
    business_rules_output: Path
    comment_mode: str


def load_config(config_path: Path, repository_path: Path) -> ReviewConfig:
    data = _load_yaml(config_path)
    repository = data.get("repository", {})
    skills = data.get("skills", {})
    knowledge = data.get("knowledge", {})
    documents = data.get("documents", {})
    reviews = data.get("reviews", {})
    github = data.get("github", {})

    return ReviewConfig(
        repository_name=str(repository.get("name", repository_path.name)),
        department=str(repository.get("department", "")),
        project=str(repository.get("project", "")),
        languages=tuple(str(item) for item in repository.get("languages", [])),
        enabled_skills=_load_enabled_skills(skills),
        knowledge_layers=tuple(str(item) for item in knowledge.get("layers", [])),
        disabled_rules=frozenset(str(item) for item in knowledge.get("disabled_rules", [])),
        summary_artifact_dir=_repo_path(repository_path, documents.get("summary_artifact_dir", ".code-review/artifacts")),
        document_sets=_load_document_sets(repository_path, documents.get("sets", [])),
        code_rules_output=_repo_path(repository_path, reviews.get("code_rules", {}).get("output", ".code-review/artifacts/code-rules-review.md")),
        business_rules_output=_repo_path(repository_path, reviews.get("business_rules", {}).get("output", ".code-review/artifacts/business-rules-review.md")),
        comment_mode=str(github.get("comment_mode", "dry_run")),
    )


def _load_document_sets(repository_path: Path, sets: list[dict[str, Any]]) -> tuple[DocumentSet, ...]:
    document_sets: list[DocumentSet] = []
    for item in sets:
        paths = item.get("paths", {})
        document_sets.append(
            DocumentSet(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                prd_path=_repo_path(repository_path, paths["prd"]),
                td_path=_repo_path(repository_path, paths["td"]),
                code_paths=tuple(_repo_path(repository_path, path) for path in item.get("code_paths", [])),
            )
        )
    return tuple(document_sets)


def _load_enabled_skills(skills: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in skills.get("enabled", []))


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in config file: {path}")
    return data


def _repo_path(repository_path: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repository_path / path
