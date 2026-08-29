from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .providers import ChatMessage, ChatResult


@dataclass(frozen=True)
class AuditRecorder:
    output_dir: Path

    def write(self, name: str, messages: list[ChatMessage], result: ChatResult) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{_safe_name(name)}.md"
        lines = [
            f"# Provider Transcript - {name}",
            "",
            f"- Model: `{result.model}`",
            f"- Usage: `{result.usage}`",
            "",
            "## Request",
            "",
        ]
        for message in messages:
            lines.extend(
                [
                    f"### {message.role}",
                    "",
                    "```md",
                    message.content,
                    "```",
                    "",
                ]
            )
        lines.extend(
            [
                "## Response",
                "",
                "```md",
                result.content,
                "```",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
