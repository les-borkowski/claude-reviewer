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


if __name__ == "__main__":
    unittest.main()
