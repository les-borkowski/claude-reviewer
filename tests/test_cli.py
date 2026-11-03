import unittest

from tests.helpers import make_repo, run_cli


class CliTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_unknown_subcommand_is_error(self):
        self.assertNotEqual(run_cli(self.repo, "nope")[0], 0)

    def test_stub_subcommand_returns_1(self):
        code, _, err = run_cli(self.repo, "stats")
        self.assertEqual(code, 1)
        self.assertIn("not implemented", err)


if __name__ == "__main__":
    unittest.main()
