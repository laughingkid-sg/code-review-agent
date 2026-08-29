from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


RULE_HEADING_RE = re.compile(r"^##\s+(?P<heading>.+?)\s*$", re.MULTILINE)
LINKED_HEADING_RE = re.compile(r"^\[(?P<title>.+?)\]\(#?(?P<slug>[a-z0-9][a-z0-9-]*)\)$")
SECTION_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    slug: str
    layer: str
    source_path: Path
    metadata: dict[str, str]
    body: str

    @property
    def contributor(self) -> str | None:
        return self.metadata.get("contributor")

    @property
    def severity(self) -> str:
        return self.metadata.get("severity", "P3")

    def compact_review_payload(self) -> str:
        sections = _extract_sections(
            self.body,
            (
                "Rule",
                "Background",
                "Risks",
                "Review Checklist",
                "Good Example",
                "Bad Example",
                "Review Comment Guidance",
            ),
        )
        lines = [
            f"## {self.slug}",
            "",
            f"ID: {self.id}",
            f"Severity: {self.severity}",
        ]
        for title, content in sections.items():
            lines.extend(["", f"{title}:", content.strip()])
        return "\n".join(lines).strip()


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


def compact_review_payload(rules: tuple[Rule, ...]) -> str:
    return "\n\n---\n\n".join(rule.compact_review_payload() for rule in rules)


def parse_rules_file(path: Path, layer: str) -> tuple[Rule, ...]:
    text = path.read_text(encoding="utf-8")
    matches = list(RULE_HEADING_RE.finditer(text))
    parsed: list[Rule] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        heading = _parse_heading(match.group("heading"))
        metadata = _parse_metadata_table(body)
        rule_id = metadata.get("id", heading.title)
        slug = metadata.get("slug", heading.slug)
        if not rule_id or not slug:
            continue
        parsed.append(
            Rule(
                id=rule_id,
                title=heading.title,
                slug=slug,
                layer=layer,
                source_path=path,
                metadata=metadata,
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


@dataclass(frozen=True)
class _Heading:
    title: str
    slug: str


def _parse_heading(raw_heading: str) -> _Heading:
    linked = LINKED_HEADING_RE.match(raw_heading.strip())
    if linked:
        return _Heading(title=linked.group("title"), slug=linked.group("slug"))
    return _Heading(title=raw_heading.strip(), slug="")


def _extract_sections(text: str, wanted_titles: tuple[str, ...]) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    wanted = set(wanted_titles)
    for index, match in enumerate(matches):
        title = match.group("title")
        if title not in wanted:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections
