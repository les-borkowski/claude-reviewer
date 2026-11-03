"""Structure checks for agent and skill prompts (quality is the eval's job)."""
import unittest

from tests.helpers import ROOT

LENSES = ["reuse", "abstraction", "dead", "noise", "language"]


def parse(rel_path):
    """(frontmatter dict, body) of a Markdown file with `---` frontmatter."""
    text = (ROOT / rel_path).read_text()
    _, front, body = text.split("---\n", 2)
    meta = {}
    for line in front.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


class AgentPromptTest(unittest.TestCase):
    def test_agents_frontmatter(self):
        for name, model in (("finder", "sonnet"), ("verifier", "opus")):
            meta, _ = parse(f"agents/{name}.md")
            self.assertEqual(meta["name"], name)
            self.assertEqual(meta["model"], model)
            self.assertTrue(meta["description"])
            tools = [t.strip() for t in meta["tools"].split(",")]
            self.assertIn("Read", tools)
            self.assertNotIn("Edit", tools)

    def test_finder_mentions_all_lenses_and_fields(self):
        _, body = parse("agents/finder.md")
        for word in LENSES + ["case", "preserves", "lines_saved", "removes", "source"]:
            self.assertIn(f"`{word}`", body, word)

    def test_verifier_mentions_formats(self):
        _, body = parse("agents/verifier.md")
        for word in ["keep", "confidence", "coverage", "tested", "untested", "unknown"]:
            self.assertIn(f"`{word}`", body, word)


class ReviewSkillTest(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse("skills/review/SKILL.md")

    def test_review_skill_frontmatter(self):
        self.assertEqual(self.meta["name"], "review")
        self.assertTrue(self.meta["description"])

    def test_review_skill_calls_every_subcommand(self):
        for cmd in ["scope", "acted-on", "tools", "context", "intent", "merge", "rank",
                    "log-run", "CLAUDE_PLUGIN_ROOT"]:
            self.assertIn(cmd, self.body)
        for cmd in ["scope", "acted-on", "tools", "context", "intent", "merge", "rank", "log-run"]:
            self.assertIn(f'reviewer.py" {cmd} ', self.body, cmd)

    def test_review_skill_dispatches_agents(self):
        self.assertIn("reviewer:finder", self.body)
        self.assertIn("reviewer:verifier", self.body)

    def test_review_skill_lists_all_lenses(self):
        for lens in LENSES:
            self.assertIn(f"`{lens}`", self.body)

    def test_report_format_has_fixed_lines(self):
        text = (ROOT / "skills/review/report-format.md").read_text()
        for fixed in ["Lean:", "Verdict:", "What this is:", "Problem:", "Fix:", "If we skip it:",
                      "Looks lean. Ship.", "check by hand", "Missing:"]:
            self.assertIn(fixed, text)


if __name__ == "__main__":
    unittest.main()
