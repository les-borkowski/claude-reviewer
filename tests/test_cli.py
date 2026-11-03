import unittest

from tests.helpers import git, make_repo, run_cli


class CliTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_unknown_subcommand_is_error(self):
        self.assertNotEqual(run_cli(self.repo, "nope")[0], 0)

    def test_reviewer_dir_never_untracked(self):
        (self.repo / ".reviewer" / "run").mkdir(parents=True)
        (self.repo / ".reviewer" / "run" / "scope.json").write_text("{}")
        self.assertEqual(run_cli(self.repo, "stats")[0], 0)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
