---
name: intelligent-code-review
description: Build or operate reusable CI pull-request review workflows that use an OpenAI-compatible LLM, markdown coding rules, PRD/TD business context, and GitHub PR comments. Use when wiring or improving this intelligent code review system; do not use for ordinary one-off code review.
metadata:
  short-description: Reusable CI PR review workflow
---

# Intelligent Code Review

Use this skill for the reusable review system made of an implementation repo, `code-review-agent`, and `code-review-knowledgebase`.

## Core Shape

- Treat the developer-authored pull request as already existing. The workflows run when a PR targeting the main branch is opened, reopened, or receives new commits.
- Keep execution code in `code-review-agent`; keep coding-rule knowledge in `code-review-knowledgebase`; keep PRD/TD documents, generated summaries, workflow config, and artifacts in the implementation repo.
- Run code-rule review and business-rule review as separate workflows so they can execute in parallel. Aggregate their artifacts afterward and publish only a lightweight artifact-links PR comment.
- Describe the model integration generically as an OpenAI-compatible LLM provider. Specific model names such as Qwen are configuration details.

## Review Inputs

- Code-rule review reads changed source files and compact markdown rules from the configured knowledge layers. Filter token-irrelevant rule metadata before sending prompts, but preserve ID, slug, and severity for comments.
- Business-rule review summarizes the affected PRD/TD document set into CI artifacts, caches fresh summaries when configured, and checks changed implementation logic against that summary.
- Do not store PRD/TD summaries or business requirements in the coding-rule knowledgebase.

## Comment Outputs

- Prefer exact-line GitHub PR review comments for actionable findings. Keep each comment tied to the changed line that caused the finding.
- For provider-backed findings, request structured JSON first and parse it into the internal finding model before rendering markdown artifacts or comments.
- Include a linked title using the rule slug when available, `RuleID`, `Severity` (`P0` highest through `P3` lowest), reasoning, recommendation, and a corrected code snippet when the fix is clear.
- Do not post long code-rule, business-rule, or aggregate finding summaries as PR conversation comments. Keep full reasoning in Actions artifacts and expose it through artifact links.
- Use managed hidden markers so reruns update or delete generated comments instead of piling up duplicates.
- Upload markdown review artifacts and LLM request/response transcripts for debugging and study.

## Knowledge Rules

- Keep rules lightweight and pure markdown in one `RULES.md` per layer/language path.
- Derive scope and language from the path. Do not repeat them in the rule metadata.
- Use field/value metadata with `ID`, `Slug`, `Contributor`, `Severity`, `Tags`, and `References`. `Contributor` is an email address; do not add a separate owner field.

## Future Feedback Loop

For planned analytics, export finding lifecycle and consumption events to an external Hive table, then analyze rule effectiveness, false positives, resolved findings, unresolved findings, consumption rate, and non-consumption rate.
