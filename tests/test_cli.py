import unittest

from tests.helpers import make_repo, run_cli


class CliTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_unknown_subcommand_is_error(self):
        self.assertNotEqual(run_cli(self.repo, "nope")[0], 0)


if __name__ == "__main__":
    unittest.main()
