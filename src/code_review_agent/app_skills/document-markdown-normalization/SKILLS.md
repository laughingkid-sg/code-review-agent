# Document Markdown Normalization

Use this skill when PRD/TD content has been normalized into markdown before summarization or review.

- Review only the normalized markdown artifacts supplied by the agent.
- Preserve requirement language and technical constraints as written; do not infer missing requirements from filenames or document titles.
- If conversion metadata says pages, tables, diagrams, or sections were unreadable, treat that content as unavailable.
- When normalized content is incomplete, surface the limitation instead of inventing business rules.
- Prefer stable headings, requirement IDs, table labels, and acceptance criteria as source anchors.
- Keep summaries concise enough for code review, but preserve details that change implementation behavior.
