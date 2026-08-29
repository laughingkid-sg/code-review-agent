# Future Improvements

This folder tracks planned improvements for the reusable code review agent beyond the current demo implementation.

## Finding Lifecycle Analytics

### Goal

Export generated finding events to an external Hive table so engineering teams can measure rule usefulness and review quality over time.

### Changes Required

- Define a machine-readable event schema for finding created, updated, deleted as stale, resolved by code change, left unresolved, upvoted, and downvoted.
- Include stable identifiers: repository, pull request, commit SHA, workflow mode, rule ID, slug, severity, file, line, finding hash, and generated comment URL.
- Add a publisher step after GitHub comment publishing that writes lifecycle events to an ingestion endpoint or object storage path consumed by Hive.
- Add privacy and retention rules before exporting code snippets or reasoning text.
- Build scheduled analysis jobs for rule consumption rate, non-consumption rate, false-positive signals, unresolved findings, and resolved findings.

## Provider-Native Structured Outputs

### Goal

Use structured provider responses for findings so the model contract is JSON and markdown is only a rendering format.

### Changes Required

- Request an OpenAI-compatible JSON object response for code-rule and business-rule findings.
- Keep the schema centered on `findings[]` with title, rule ID, slug, severity, repo-relative file, line, reasoning, recommendation, corrected code, and language.
- Parse JSON into the internal `ReviewFinding` model before writing markdown artifacts or GitHub comments.
- Keep raw provider transcripts in `output/` for debugging invalid or empty responses.
- Consider provider-enforced JSON schema when the selected LLM API supports it consistently.

## Aggregation Quality

### Goal

Make the final managed PR summary reflect only actionable findings that were actually publishable on the PR diff.

### Changes Required

- Record whether each finding was posted inline, skipped because it was off-diff, deduplicated, or deleted as stale.
- Feed publish results into the aggregate workflow instead of aggregating artifact text alone.
- Cluster duplicate code-rule and business-rule findings by file, line, slug, and corrected-code similarity.
- Present one concise final summary with links to the inline comments that survived publishing.

## Project Management Document Integration

### Goal

Fetch PRD/TD documents from project-management or document systems rather than storing demo markdown files in the implementation repo.

### Changes Required

- Add repository configuration for document source type, issue key extraction, and allowed document locations.
- Fetch linked PRD/TD documents during CI with scoped credentials.
- Convert supported document types such as markdown, PDF, and DOCX into text before summarization.
- Cache summaries by document identity, document version, and PR head SHA.
- Surface missing or inaccessible documents as a managed PR summary warning.

## Rule Governance

### Goal

Keep the knowledgebase lightweight while improving rule quality as adoption grows.

### Changes Required

- Add duplicate-rule detection across common, department, and repo layers.
- Propose promotion of repo rules to department or common layers when consumption data shows broad usefulness.
- Track rule churn, contributor, severity distribution, and disabled-rule usage.
- Add compatibility checks when a rule slug, ID, or severity changes.

## Notifications

### Goal

Notify developers when reviews finish without forcing them to watch CI logs.

### Changes Required

- Add optional Slack, Lark, or Teams notification outputs after review completion.
- Include PR link, aggregate summary status, finding counts by severity, and failed workflow diagnostics.
- Keep notifications configurable per implementation repo and disabled by default for the public demo.
