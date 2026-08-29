# Business Requirement Tracing

Use this skill when reviewing implementation files against PRD/TD summary artifacts.

- Treat the normalized PRD/TD summary as the business source of truth.
- Tie every business finding to the nearest source heading, requirement, constraint, or open question in the summary.
- Flag missing or incorrect behavior only when the supplied implementation files show enough evidence.
- Do not report a missing requirement when a supporting implementation file appears to satisfy it.
- Use empty `rule_id` and `slug` values when the issue is business-specific rather than a coding-rule violation.
- Explain the product impact in reasoning and the concrete implementation change in the recommendation.
