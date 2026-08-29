from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class SkillPromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApplicationSkill:
    name: str
    path: Path
    content: str


@dataclass(frozen=True)
class SkillPromptBundle:
    skills: tuple[ApplicationSkill, ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(skill.name for skill in self.skills)

    def render(self) -> str:
        if not self.skills:
            return ""
        lines = ["# Enabled Application SKILLS", ""]
        for skill in self.skills:
            lines.extend([f"## {skill.name}", "", skill.content.strip(), ""])
        return "\n".join(lines).strip()


EMPTY_SKILL_PROMPTS = SkillPromptBundle()
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
BUILTIN_SKILLS_DIR = Path(__file__).with_name("app_skills")


def load_skill_prompts(skill_names: tuple[str, ...], skills_dir: Path = BUILTIN_SKILLS_DIR) -> SkillPromptBundle:
    skills: list[ApplicationSkill] = []
    for name in _dedupe_skill_names(skill_names):
        if not SKILL_NAME_RE.fullmatch(name):
            raise SkillPromptError(f"Invalid application skill name: {name}")
        path = skills_dir / name / "SKILLS.md"
        if not path.exists():
            raise SkillPromptError(f"Application skill not found: {name}")
        skills.append(ApplicationSkill(name=name, path=path, content=path.read_text(encoding="utf-8")))
    return SkillPromptBundle(tuple(skills))


def _dedupe_skill_names(skill_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(name.strip() for name in skill_names if name.strip()))
