# Architecture

## Overview

The review system is split across three repositories:

- implementation repository: owns product code, PRD/TD documents, and CI artifacts.
- knowledgebase repository: owns reusable markdown review rules.
- agent repository: owns executable CI review logic and GitHub Action contract.

## Parallel Review Jobs

Two review jobs can run during the same pull request event:

- `code-rules`: checks changed code against markdown rules from the knowledgebase.
- `business-rules`: creates PR-specific PRD/TD summaries and checks implementation logic against those requirements.

Both jobs run after the developer opens a PR or pushes new commits to the PR.

## Artifact Ownership

Generated summaries and review reports belong to the implementation repository CI run. They should be uploaded as GitHub Actions artifacts and may also be written to `.code-review/artifacts` during local dry-runs.
