# Code Review Findings

Use this skill when reviewing changed implementation files against markdown coding rules.

- Report only actionable issues that are directly supported by the supplied code and rules.
- Tie every finding to the smallest exact line that demonstrates the issue.
- Prefer changed lines. If supporting context is needed, mention it in reasoning but keep the finding line on the actionable code.
- Do not create a finding for style preferences unless a supplied rule explicitly requires it.
- When a rule applies, preserve its `rule_id`, `slug`, and `severity` exactly.
- Return an empty findings array when evidence is incomplete or the code already satisfies the rule.
