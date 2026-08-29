from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


RULE_HEADING_RE = re.compile(r"^##\s+(?P<id>[A-Z0-9-]+):\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    layer: str
    source_path: Path
    metadata: dict[str, str]
    body: str

    @property
    def owner(self) -> str | None:
        return self.metadata.get("owner")

    @property
    def contributor(self) -> str | None:
        return self.metadata.get("contributor")


def load_rules(knowledgebase_path: Path, layers: tuple[str, ...], disabled_rules: frozenset[str]) -> tuple[Rule, ...]:
    rules: list[Rule] = []
    for layer in layers:
        path = knowledgebase_path / layer / "RULES.md"
        if not path.exists():
            continue
        for rule in parse_rules_file(path, layer):
            if rule.id not in disabled_rules:
                rules.append(rule)
    return tuple(rules)


def parse_rules_file(path: Path, layer: str) -> tuple[Rule, ...]:
    text = path.read_text(encoding="utf-8")
    matches = list(RULE_HEADING_RE.finditer(text))
    parsed: list[Rule] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        parsed.append(
            Rule(
                id=match.group("id"),
                title=match.group("title"),
                layer=layer,
                source_path=path,
                metadata=_parse_metadata_table(body),
                body=body,
            )
        )
    return tuple(parsed)


def _parse_metadata_table(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 2:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"Field", "---"}:
            continue
        key = cells[0].lower().replace(" ", "_")
        metadata[key] = cells[1].replace("`", "").strip()
    return metadata
