from pathlib import Path
import tempfile
import unittest

from code_review_agent.skill_prompts import SkillPromptError, load_skill_prompts


class SkillPromptTest(unittest.TestCase):
    def test_loads_builtin_skill_prompt(self) -> None:
        bundle = load_skill_prompts(("code-review-findings",))

        self.assertEqual(bundle.names, ("code-review-findings",))
        rendered = bundle.render()
        self.assertIn("# Enabled Application SKILLS", rendered)
        self.assertIn("## code-review-findings", rendered)
        self.assertIn("Use this skill when reviewing changed implementation files", rendered)

    def test_dedupes_skill_names_in_order(self) -> None:
        bundle = load_skill_prompts(("code-review-findings", "code-review-findings", "github-inline-comments"))

        self.assertEqual(bundle.names, ("code-review-findings", "github-inline-comments"))

    def test_rejects_invalid_skill_name(self) -> None:
        with self.assertRaisesRegex(SkillPromptError, "Invalid application skill name"):
            load_skill_prompts(("../secret",))

    def test_reports_missing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(SkillPromptError, "Application skill not found"):
                load_skill_prompts(("missing-skill",), skills_dir=Path(tmpdir))


if __name__ == "__main__":
    unittest.main()
