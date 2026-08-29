# Code Review Agent

Reusable Python agent and GitHub Action for the intelligent code review demo.

The agent reviews pull request changes after a developer opens a PR or pushes new commits to an existing PR. It does not create the PR. It reads repository configuration, PRD/TD documents, changed files, and markdown rules from the knowledgebase, then produces review artifacts and later PR comments.

## Responsibilities

- Load target repository config from `.code-review.yml`.
- Read pull request diffs and changed files.
- Load markdown rules from `code-review-knowledgebase`.
- Preserve contributor metadata in full rule records and keep review payloads compact for model calls.
- Generate PR-specific PRD/TD summaries as CI artifacts in the implementation repository run.
- Run code-rule review and business-rule review as separate jobs so they can execute in parallel.
- Publish GitHub PR comments after dry-run output is approved.

## Non-Responsibilities

- Store PRD or TD summaries in the knowledgebase.
- Own product or technical requirement source documents.
- Replace manual developer PR creation.

## Modes

- `code-rules`: applies markdown knowledgebase rules to changed code.
- `business-rules`: summarizes PRD/TD documents and compares implementation behavior against requirements.
- `aggregate`: combines review artifacts into a single report or PR comment.

## Rule Payloads

The agent keeps full rule metadata for reports and future governance, then builds a compact rule payload for model review. The compact payload keeps `ID`, `Slug`, `Severity`, and check-relevant rule sections. It excludes `Contributor`, `Tags`, and `References` to reduce tokens sent to the model.

## Required Secrets

- `DASHSCOPE_API_KEY`: Qwen/DashScope API key for LLM review.
- `GITHUB_TOKEN`: provided by GitHub Actions for PR metadata and comments.
- `KNOWLEDGEBASE_REPO_TOKEN`: optional, only needed if the knowledgebase repo is private and cannot be checked out with the default token.

## Local Dry-Run

Run from a local checkout:

```bash
PYTHONPATH=src python -m code_review_agent run \
  --mode code-rules \
  --config .code-review.yml \
  --repository ../code-review-demo \
  --knowledgebase ../code-review-knowledgebase \
  --default-contributor codex \
  --output .code-review/artifacts/code-rules-review.md
```

For business-rule dry-runs:

```bash
PYTHONPATH=src python -m code_review_agent run \
  --mode business-rules \
  --config .code-review.yml \
  --repository ../code-review-demo \
  --knowledgebase ../code-review-knowledgebase \
  --output .code-review/artifacts/business-rules-review.md
```
