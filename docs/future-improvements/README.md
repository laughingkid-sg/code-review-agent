# Future Improvements

This document combines every future-improvement candidate from:

- `code-review-demo/README.md` Future Improvements
- `code-review-agent/docs/future-improvements/README.md`
- `code-review-demo/output/reference-process-comparison.md`

Selection status: draft for review. After the selected items are confirmed, `code-review-demo/README.md` should link each future-improvement bullet to the exact section anchor in this document.

## Selection Table

| ID | Improvement | Primary Repo | Suggested Priority | Keep / Drop / Defer |
| --- | --- | --- | --- | --- |
| FI-001 | [Review filter stage for precision](#fi-001-review-filter-stage-for-precision) | `code-review-agent` | P1 | TBD |
| FI-002 | [Diff-aware context preparation](#fi-002-diff-aware-context-preparation) | `code-review-agent` | P1 | TBD |
| FI-003 | [Finding lifecycle artifacts](#fi-003-finding-lifecycle-artifacts) | `code-review-agent` | P1 | TBD |
| FI-004 | [Aggregate summary from publish results](#fi-004-aggregate-summary-from-publish-results) | `code-review-agent`, `code-review-demo` | P1 | TBD |
| FI-005 | [Finding analytics export to Hive](#fi-005-finding-analytics-export-to-hive) | `code-review-agent` | P2 | TBD |
| FI-006 | [Consumption and non-consumption metrics](#fi-006-consumption-and-non-consumption-metrics) | `code-review-agent` | P2 | TBD |
| FI-007 | [Developer feedback signals](#fi-007-developer-feedback-signals) | `code-review-agent`, `code-review-demo` | P2 | TBD |
| FI-008 | [Rule effectiveness dashboard](#fi-008-rule-effectiveness-dashboard) | External analytics, `code-review-agent` | P2 | TBD |
| FI-009 | [Project-management document integration](#fi-009-project-management-document-integration) | `code-review-agent`, implementation repos | P2 | TBD |
| FI-010 | [Versioned cross-repo contracts](#fi-010-versioned-cross-repo-contracts) | All repos | P2 | TBD |
| FI-011 | [Knowledgebase contribution guide](#fi-011-knowledgebase-contribution-guide) | `code-review-knowledgebase` | P2 | TBD |
| FI-012 | [Rule duplicate detection and promotion](#fi-012-rule-duplicate-detection-and-promotion) | `code-review-knowledgebase`, `code-review-agent` | P2 | TBD |
| FI-013 | [Historical benchmark suite](#fi-013-historical-benchmark-suite) | `code-review-agent`, `code-review-demo` | P2 | TBD |
| FI-014 | [Governance operating playbook](#fi-014-governance-operating-playbook) | `code-review-agent`, `code-review-knowledgebase` | P3 | TBD |
| FI-015 | [Multi-language expansion](#fi-015-multi-language-expansion) | All repos | P3 | TBD |
| FI-016 | [Provider capability detection](#fi-016-provider-capability-detection) | `code-review-agent` | P2 | TBD |
| FI-017 | [Optional developer notifications](#fi-017-optional-developer-notifications) | `code-review-agent`, implementation repos | P3 | TBD |
| FI-018 | [Guided repair patch suggestions](#fi-018-guided-repair-patch-suggestions) | `code-review-agent` | P3 | TBD |
| FI-019 | [Public-repo safety model](#fi-019-public-repo-safety-model) | `code-review-demo`, `code-review-agent` | P2 | TBD |
| FI-020 | [Category and taxonomy metadata](#fi-020-category-and-taxonomy-metadata) | `code-review-knowledgebase`, `code-review-agent` | P3 | TBD |

## FI-001 Review Filter Stage For Precision

### Goal

Add a second-stage validation step that reviews generated findings before publishing them, prioritizing precision over recall.

### Why

The reference process treats review filtering as a core production-readiness layer because raw LLM findings can be hallucinated, low-value, or unsupported by the changed code.

### Implementation Plan

1. Add a `review-filter` module in `code-review-agent`.
2. Feed it parsed `ReviewFinding` JSON plus the relevant code context and, for code-rule findings, the matched rule text.
3. Request structured JSON output such as:

   ```json
   {
     "decisions": [
       {
         "finding_hash": "string",
         "decision": "accept|reject",
         "reason": "string"
       }
     ]
   }
   ```

4. Publish only accepted findings.
5. Write rejected findings to artifacts for audit, not PR comments.
6. Add tests for accepted, rejected, malformed, and missing-decision cases.

### Acceptance Criteria

- Code-rule and business-rule workflows can run with filtering enabled.
- Rejected findings do not create inline comments.
- Rejection reasons are visible in CI artifacts.
- Existing deterministic/mock tests still pass.

## FI-002 Diff-Aware Context Preparation

### Goal

Send smaller, more relevant review context by starting from PR diff hunks, then expanding only to useful surrounding code.

### Why

Current review sends changed Go files and some supporting files. This works for the demo but may waste tokens and dilute findings on larger PRs.

### Implementation Plan

1. Add a diff parser that reads changed files and hunks from GitHub or local git.
2. Represent added, modified, deleted, and unchanged lines explicitly.
3. Expand hunks to the nearest function boundary for Go files.
4. Cap expansion by a configurable multiplier or max character budget.
5. Keep full-file fallback when parsing fails.
6. Update prompts to review hunk units instead of whole files where possible.

### Acceptance Criteria

- Provider transcripts show annotated diff/function context.
- Inline comments still map to repo-relative changed lines.
- Token usage drops for multi-file PRs.

## FI-003 Finding Lifecycle Artifacts

### Goal

Record machine-readable publish outcomes for every finding in each workflow run.

### Why

The aggregate summary and future analytics need to know what actually happened to each finding, not just what appeared in markdown.

### Implementation Plan

1. Create a lifecycle artifact format such as `.code-review/artifacts/findings-code-rules.json`.
2. Include repository, PR number, head SHA, mode, finding hash, rule ID, slug, severity, file, line, title, status, and comment URL when available.
3. Track statuses: `created`, `updated`, `deduped`, `skipped_off_diff`, `deleted_stale`, `unchanged`, `failed`.
4. Update GitHub comment publisher to return per-finding publish results.
5. Upload lifecycle JSON artifacts in code-rule, business-rule, and aggregate workflows.

### Acceptance Criteria

- Every emitted finding has exactly one lifecycle record.
- Off-diff findings are visible in artifacts with a skip reason.
- Stale deletions are recorded.

## FI-004 Aggregate Summary From Publish Results

### Goal

Make the final managed PR summary reflect posted inline comments and real publish outcomes, not raw artifact findings only.

### Why

Current aggregate mode combines code/business markdown artifacts. That can include findings that were skipped or deduped before inline publishing.

### Implementation Plan

1. Download lifecycle JSON artifacts from code-rule and business-rule runs.
2. Aggregate by actual publish status.
3. Cluster duplicates by file, line, slug, rule ID, and corrected-code similarity.
4. Show counts by severity and mode.
5. Link final summary rows to surviving inline comments when URLs are available.
6. Include a small skipped/deduped section for transparency.

### Acceptance Criteria

- Final managed summary count matches visible generated inline comments.
- Duplicate code/business findings are grouped.
- Off-diff skipped findings no longer appear as normal actionable items.

## FI-005 Finding Analytics Export To Hive

### Goal

Export finding lifecycle events to an external Hive table for long-term analysis.

### Why

The planned feedback loop depends on durable, queryable review events across repositories and time.

### Implementation Plan

1. Define a Hive-compatible schema for finding lifecycle events.
2. Add a publisher step after comment publishing.
3. Support one or more export targets, such as object storage or an ingestion API.
4. Include privacy controls before exporting reasoning or corrected-code snippets.
5. Add retry and dead-letter behavior for export failures.
6. Keep export disabled by default for the public demo.

### Acceptance Criteria

- CI can upload lifecycle events without blocking comments when export is optional.
- Required identifiers are queryable: repo, PR, SHA, rule ID, slug, severity, file, line, status.
- Sensitive content export is configurable.

## FI-006 Consumption And Non-Consumption Metrics

### Goal

Measure whether developers act on review findings after the agent comments.

### Why

A comment being technically correct is not enough. The process needs to know whether the finding was consumed, ignored, or rejected.

### Implementation Plan

1. Define consumption as a later push changing the flagged line/range or resolving the generated comment.
2. Define non-consumption as a finding that remains unresolved and unchanged after merge or after a configured time window.
3. Compare finding lifecycle records against later commits in the PR.
4. Track resolution state from GitHub review threads when available.
5. Emit metrics by rule ID, slug, severity, repo, department, and project.

### Acceptance Criteria

- A changed flagged line is recorded as consumed.
- A resolved generated thread can be recorded as consumed.
- Unchanged/unresolved findings are recorded as non-consumed.

## FI-007 Developer Feedback Signals

### Goal

Allow developers to mark generated comments as useful, not useful, false positive, or temporarily not fixed.

### Why

Feedback separates noisy comments from useful but unconsumed comments.

### Implementation Plan

1. Decide initial feedback mechanism: GitHub reactions, slash commands, issue comment commands, or review-thread labels.
2. Map feedback to normalized values: `useful`, `not_useful`, `false_positive`, `temporarily_not_fixed`.
3. Ingest feedback into lifecycle artifacts or the analytics export.
4. Add docs telling reviewers what each feedback value means.
5. Avoid requiring feedback for normal development flow.

### Acceptance Criteria

- Feedback can be linked to a finding hash or generated comment marker.
- Feedback is exportable for analytics.
- False-positive feedback can be traced back to a rule.

## FI-008 Rule Effectiveness Dashboard

### Goal

Build dashboards for rule and agent effectiveness.

### Why

Rule owners need a fast way to see which rules produce useful comments and which rules create noise.

### Implementation Plan

1. Create dashboard queries from Hive or the chosen analytics store.
2. Show finding count, consumption rate, non-consumption rate, false-positive rate, resolved rate, and stale rate.
3. Break metrics down by repo, department, project, language, rule ID, slug, severity, and workflow mode.
4. Highlight low-consumption/high-noise rules for review.
5. Add trend views before and after rule edits.

### Acceptance Criteria

- Rule owners can identify top useful and top noisy rules.
- Dashboard supports weekly or biweekly governance review.
- Data excludes private code snippets unless explicitly allowed.

## FI-009 Project-Management Document Integration

### Goal

Fetch PRD/TD documents from project-management or document platforms instead of relying only on local markdown.

### Why

The demo uses local markdown for simplicity, but production PRs usually reference documents through planning systems.

### Implementation Plan

1. Add config for document source type, issue-key extraction, and allowed document locations.
2. Resolve PRD/TD links from PR metadata, branch names, commit messages, or issue keys.
3. Fetch supported formats: markdown, PDF, DOCX, and web-exported text when authorized.
4. Convert documents into text for summarization.
5. Cache summaries by document identity, document version, PR number, and head SHA.
6. Warn in a managed PR summary when required documents are missing or inaccessible.

### Acceptance Criteria

- Business-rule workflow can read external PRD/TD sources when credentials are configured.
- Missing docs produce a clear managed summary warning.
- Local markdown remains supported for the demo.

## FI-010 Versioned Cross-Repo Contracts

### Goal

Make the contracts between implementation repos, `code-review-agent`, and `code-review-knowledgebase` explicit and versioned.

### Why

As more repos adopt the action, breaking changes in config, rule format, artifacts, or comment markers become costly.

### Implementation Plan

1. Add a documented contract version to `.code-review.yml`.
2. Version rule metadata expectations in the KB validator.
3. Version lifecycle JSON artifact schemas.
4. Add compatibility tests for older supported config/rule/artifact versions.
5. Document deprecation policy.

### Acceptance Criteria

- Agent fails with actionable errors for unsupported contract versions.
- Repos can upgrade intentionally.
- CI tests cover at least the current and previous contract version once versioning begins.

## FI-011 Knowledgebase Contribution Guide

### Goal

Document how to turn an incident, missed review, or repeated code mistake into a reusable rule.

### Why

The KB needs a lightweight, repeatable contribution process that improves rules without making the repo heavy.

### Implementation Plan

1. Add `docs/CONTRIBUTING_RULES.md` in `code-review-knowledgebase`.
2. Define the contribution flow: write failure mode, extract review signal, generalize scope, add good/bad examples, validate, review, merge.
3. Include guidance for avoiding overly broad rules.
4. Include examples for code-error rules and note that business rules belong in the business-rule pipeline, not KB.
5. Link validator command and severity definitions.

### Acceptance Criteria

- New contributors can add a rule without reading chat history.
- Validator requirements are clear.
- The guide reinforces the lightweight markdown format.

## FI-012 Rule Duplicate Detection And Promotion

### Goal

Find duplicate/overlapping rules and promote useful repo-level rules upward when metrics justify it.

### Why

Layered knowledge can drift if each repo copies similar rules.

### Implementation Plan

1. Add a KB scanner that compares titles, slugs, checklist text, and examples across layers.
2. Report likely duplicates in CI without blocking initially.
3. Use analytics metrics to suggest promotion from project to department or common.
4. Add a rule deprecation marker or migration note when rules are merged.
5. Keep stable IDs or provide redirects if comments/analytics depend on old IDs.

### Acceptance Criteria

- Duplicate candidates are visible in KB CI.
- Promotion/deprecation keeps existing suppressions and analytics understandable.
- Rule count and duplicate rate are measurable.

## FI-013 Historical Benchmark Suite

### Goal

Create a small benchmark set of known buggy/fixed changes and expected findings.

### Why

Intentional demo bugs prove the live PR path, but a repeatable benchmark is needed to measure recall and regressions over time.

### Implementation Plan

1. Store sanitized fixtures in `code-review-agent` or a dedicated benchmark folder.
2. Include before/after diffs, relevant rules/docs, and expected finding JSON.
3. Add a benchmark runner that executes code-rule and business-rule modes in dry-run.
4. Track expected recall and false-positive behavior.
5. Add a small demo benchmark first, then expand with real sanitized incidents.

### Acceptance Criteria

- Benchmark can run locally and in CI without secrets.
- Expected findings are compared structurally, not by exact prose.
- Rule changes can be tested against known historical cases.

## FI-014 Governance Operating Playbook

### Goal

Define the recurring operating rhythm for reviewing metrics, noisy rules, missed recalls, and knowledge updates.

### Why

The reference process is an operating system, not just a CI tool. Without cadence, feedback data will not improve rules.

### Implementation Plan

1. Add `docs/OPERATING_PLAYBOOK.md`.
2. Define weekly or biweekly review inputs: dashboard, noisy rules, false positives, missed recalls, consumption, non-consumption, new incidents.
3. Define decisions: keep, edit, disable, promote, merge, or retire rules.
4. Define owners for implementation repo, agent repo, and KB repo.
5. Add a lightweight decision log template.

### Acceptance Criteria

- A team can run the governance meeting from the playbook.
- Rule changes link back to data or incident evidence.
- Decisions are auditable without exposing sensitive details.

## FI-015 Multi-Language Expansion

### Goal

Expand beyond Go after the Go demo is stable.

### Why

The target scale includes many repos, and future adoption may require TypeScript, Python, Java, or other languages.

### Implementation Plan

1. Add language config routing in `.code-review.yml`.
2. Add KB paths such as `common/typescript/RULES.md`.
3. Add language-specific file filters and context extraction.
4. Add language-aware corrected-code fences.
5. Add tests per language before enabling CI comments.

### Acceptance Criteria

- Go behavior remains unchanged.
- New language support can be enabled per repo.
- Unsupported file types are ignored safely.

## FI-016 Provider Capability Detection

### Goal

Detect and adapt to provider support for JSON object mode, JSON schema, context limits, retries, and rate limits.

### Why

The architecture should remain provider-generic while still using stronger guarantees when available.

### Implementation Plan

1. Add provider capability config or probing.
2. Prefer JSON schema mode when supported.
3. Fall back to JSON object mode when schema mode is unavailable.
4. Add retry handling for transient provider errors and invalid JSON.
5. Record provider capabilities in audit transcripts.

### Acceptance Criteria

- Provider configuration errors are actionable.
- The agent can explain whether schema mode or JSON object mode was used.
- Tests cover schema-capable, JSON-only, and unsupported modes.

## FI-017 Optional Developer Notifications

### Goal

Notify developers when code review automation finishes.

### Why

Developers should not need to poll CI logs to know whether review comments are ready.

### Implementation Plan

1. Add optional notification output after aggregate review.
2. Support Slack, Lark, or Teams via repo-level configuration.
3. Include PR link, summary status, finding counts by severity, and failed workflow diagnostics.
4. Keep notifications disabled by default in the public demo.
5. Avoid sending code snippets to chat unless explicitly enabled.

### Acceptance Criteria

- Notification setup is optional and does not affect PR comments.
- Failed notification does not fail code review unless configured.
- Message content is concise and safe.

## FI-018 Guided Repair Patch Suggestions

### Goal

Generate optional patch suggestions for clear, localized findings while keeping developer approval in control.

### Why

Inline corrected snippets are helpful, but GitHub suggestion blocks or patch artifacts can reduce repair effort.

### Implementation Plan

1. Detect findings with safe single-hunk corrected code.
2. Render GitHub suggestion blocks when the replacement is exact and line-scoped.
3. For larger fixes, upload patch artifacts instead of auto-applying.
4. Add guardrails for tests, generated files, and ambiguous context.
5. Keep auto-commit or auto-PR behavior out of default CI.

### Acceptance Criteria

- Suggestions only appear when line mapping is reliable.
- Developers can apply suggestions manually in GitHub.
- No automatic source mutation happens in the review workflow.

## FI-019 Public-Repo Safety Model

### Goal

Document and enforce safe behavior before publishing the demo publicly.

### Why

The demo uses repository secrets and an LLM provider. Public PR behavior must be explicit and conservative.

### Implementation Plan

1. Document the threat model for public forks, untrusted PRs, secrets, and prompt injection.
2. Keep same-repo author guards unless deliberately changed.
3. Keep Go-path filters to avoid token spend on docs-only edits.
4. Avoid sending secrets, `.env`, generated artifacts, or unrelated files to the LLM.
5. Add tests or workflow comments explaining why guarded conditions exist.

### Acceptance Criteria

- Public fork PRs cannot access provider secrets.
- Review scope is restricted to changed Go files and configured support files.
- README explains the safety posture clearly.

## FI-020 Category And Taxonomy Metadata

### Goal

Optionally add lightweight taxonomy/category metadata to rules and findings for analytics and triage.

### Why

The references use categories/dimensions to evaluate review quality by issue type. Our current KB is intentionally lighter.

### Implementation Plan

1. Keep current rule metadata unchanged unless analytics needs categories.
2. If selected, add optional `Category` or `Dimension` fields to KB rules.
3. Update validator to allow but not require the new fields.
4. Include category in lifecycle artifacts and dashboards.
5. Do not send category metadata to the LLM unless it improves rule selection or comments.

### Acceptance Criteria

- Existing rules stay valid.
- Category metadata is optional and analytics-oriented.
- Comment format does not become noisy.

## Suggested Phase Grouping

### Phase A: Make Current PR Output More Trustworthy

- FI-001 Review filter stage for precision
- FI-002 Diff-aware context preparation
- FI-003 Finding lifecycle artifacts
- FI-004 Aggregate summary from publish results
- FI-016 Provider capability detection

### Phase B: Build The Feedback Loop

- FI-005 Finding analytics export to Hive
- FI-006 Consumption and non-consumption metrics
- FI-007 Developer feedback signals
- FI-008 Rule effectiveness dashboard

### Phase C: Improve Knowledge Operations

- FI-011 Knowledgebase contribution guide
- FI-012 Rule duplicate detection and promotion
- FI-013 Historical benchmark suite
- FI-014 Governance operating playbook
- FI-020 Category and taxonomy metadata

### Phase D: Scale Beyond The Demo

- FI-009 Project-management document integration
- FI-010 Versioned cross-repo contracts
- FI-015 Multi-language expansion
- FI-017 Optional developer notifications
- FI-018 Guided repair patch suggestions
- FI-019 Public-repo safety model

## Recommended Keep List

If we want the next useful slice without overbuilding, keep these first:

1. FI-003 Finding lifecycle artifacts
2. FI-004 Aggregate summary from publish results
3. FI-001 Review filter stage for precision
4. FI-002 Diff-aware context preparation
5. FI-011 Knowledgebase contribution guide
6. FI-019 Public-repo safety model

These make the current demo more accurate, explainable, and public-safe before adding heavier analytics or external integrations.
