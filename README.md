# Code Review Agent

Reusable Python agent and GitHub Action for the intelligent code review demo.

The agent reviews pull request changes after a developer opens a PR or pushes new commits to an existing PR. It does not create the PR. It reads repository configuration, PRD/TD documents, changed files, and markdown rules from the knowledgebase, then produces review artifacts and later PR comments.

## Responsibilities

- Load target repository config from `.code-review.yml`.
- Read pull request diffs and changed files.
- Load markdown rules from `code-review-knowledgebase`.
- Preserve owner and contributor metadata from knowledgebase rules and generated findings.
- Generate PR-specific PRD/TD summaries as CI artifacts in the implementation repository run.
- Run code-rule review and business-rule review as separate jobs so they can execute in parallel.
- Publish GitHub PR comments after dry-run output is approved.

## Non-Responsibilities

- Store PRD or TD summaries in the knowledgebase.
- Own product or technical requirement source documents.
- Replace manual developer PR creation.

## Planned Modes

- `code-rules`: applies markdown knowledgebase rules to changed code.
- `business-rules`: summarizes PRD/TD documents and compares implementation behavior against requirements.
- `aggregate`: combines review artifacts into a single report or PR comment.

## Required Secrets

- `DASHSCOPE_API_KEY`: Qwen/DashScope API key for LLM review.
- `GITHUB_TOKEN`: provided by GitHub Actions for PR metadata and comments.
- `KNOWLEDGEBASE_REPO_TOKEN`: optional, only needed if the knowledgebase repo is private and cannot be checked out with the default token.

## Local Dry-Run Shape

The Python CLI will support a command similar to:

```bash
python -m code_review_agent run \
  --mode code-rules \
  --config .code-review.yml \
  --knowledgebase ../code-review-knowledgebase \
  --default-owner unassigned \
  --default-contributor codex \
  --output .code-review/artifacts/code-rules-review.md
```
