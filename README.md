# Code Review Agent

Reusable Python agent and composite GitHub Action for the intelligent code review demo.

The agent runs after a developer opens a pull request or pushes new commits to an existing pull request. It does not create PRs. It reads repository configuration, changed files, PRD/TDD documents, and markdown rules, then writes review artifacts and publishes managed GitHub PR comments.

## Repository Role

- Own executable review logic shared by implementation repositories.
- Provide the composite GitHub Action contract in `action.yml`.
- Run code-rule, business-rule, and aggregate review modes.
- Keep full rule records for reporting while sending compact payloads to the LLM.
- Write provider request/response transcripts to `output/`.
- Publish managed summary comments and exact-line inline PR review comments.

## Non-Responsibilities

- Store coding rules. Those live in `code-review-knowledgebase`.
- Store PRD/TDD summaries permanently. Those are generated in implementation repo CI artifacts.
- Replace manual developer PR creation.

## Architecture

```mermaid
flowchart TD
  Action[action.yml composite action] --> CLI[cli.py]
  CLI --> Config[config.py]
  CLI --> Skills[internal Python skills package]
  Skills --> CodeSkill[code_rules module]
  Skills --> BizSkill[business_rules module]
  Skills --> AggSkill[aggregation module]
  Skills --> CommentSkill[github_comments module]
  CodeSkill --> Rules[rules.py compact KB payload]
  BizSkill --> Docs[documents.py PRD/TDD summaries]
  CodeSkill --> Provider[providers.py OpenAI-compatible LLM]
  BizSkill --> Provider
  Provider --> Findings[findings.py structured finding parser]
  Findings --> CommentSkill
  CommentSkill --> GitHub[github.py PR comments and stale cleanup]
  Provider --> Audit[audit.py transcripts]
```

## Review Flow

```mermaid
sequenceDiagram
  participant Workflow as GitHub workflow
  participant CLI as code_review_agent CLI
  participant Skill as Review skill
  participant LLM as OpenAI-compatible LLM API
  participant GH as GitHub API
  Workflow->>CLI: Run mode with config, changed files, and output path
  CLI->>Skill: Dispatch to code, business, or aggregate skill
  Skill->>LLM: Send review context when provider is enabled
  LLM-->>Skill: Return findings with corrected snippets
  Skill->>CLI: Write markdown artifact
  CLI->>GH: Post/update managed summary comment
  CLI->>GH: Post/update inline comments for code/business findings
  CLI->>GH: Delete stale generated inline comments for that mode
```

## Modes

| Mode | Purpose | Inline comments |
| --- | --- | --- |
| `code-rules` | Review changed code against markdown coding rules from the knowledgebase. | Yes |
| `business-rules` | Summarize affected PRD/TDD documents and review implementation logic against them. | Yes |
| `aggregate` | Combine code-rule and business-rule artifacts into a final PR summary. | No, summary only |

## AI Skill

The reusable AI Skill lives at `skills/intelligent-code-review/SKILL.md`. It captures the generic review workflow for another Codex run: provider-agnostic LLM setup, markdown knowledge rules, PRD/TD business context, exact-line comments, managed summaries, artifacts, and stale generated comment cleanup.

## Action Inputs

| Input | Purpose |
| --- | --- |
| `mode` | `code-rules`, `business-rules`, or `aggregate`. |
| `config-path` | Target repo `.code-review.yml`. |
| `repository-path` | Target implementation repository checkout path. |
| `knowledgebase-path` | Checked-out `code-review-knowledgebase` path. |
| `output-path` | Markdown artifact to write. |
| `provider` | `mock` or `llm`; `qwen` is accepted as a backwards-compatible alias. |
| `comment-mode` | `dry_run` or `pr_comment`. |
| `changed-files` | Newline-separated changed file paths. |
| `audit-dir` | Directory for provider transcripts. |
| `summary-cache-ttl-days` | Freshness window for PRD/TDD summary cache. |
| `aggregate-inputs` | Newline-separated artifacts to combine in aggregate mode. |
| `pull-request-number` | PR number override for non-PR events such as `workflow_run`. |
| `head-sha` | Head SHA override for non-PR events such as `workflow_run`. |

## Provider Configuration

The current demo uses an OpenAI-compatible LLM provider. Alibaba Model Studio/Qwen is one compatible configuration, not a required architecture choice.

- `OPENAI_API_KEY`: required provider key.
- `OPENAI_BASE_URL`: OpenAI-compatible base URL.
- `OPENAI_MODEL`: model name.
- `GITHUB_TOKEN`: provided by GitHub Actions for PR metadata and comments.

## Findings and Comments

The agent asks provider-backed reviews for a JSON object with `findings[]`, parses those records into structured `ReviewFinding` values, then renders markdown artifacts and GitHub comments from the parsed data. Markdown parsing is kept only as a compatibility fallback for older artifacts.

Inline comments include:

- linked finding title using the rule slug when available.
- `RuleID` and `Severity`.
- quoted reasoning.
- recommendation.
- corrected fenced code snippet when the model provides one.
- direct link to the changed line.

Generated inline comments include hidden markers. On rerun, the agent updates matching generated comments and deletes stale generated comments for the same review mode.

## Future Improvements

Detailed future improvements and required changes are tracked in [docs/future-improvements/README.md](docs/future-improvements/README.md).
