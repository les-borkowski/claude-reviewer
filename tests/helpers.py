"""Shared test helpers: throwaway git repos and an in-process CLI runner."""
import atexit
import contextlib
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import reviewer  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout


def make_repo(branch="main"):
    """Temp git repo on `branch` with one commit."""
    repo = pathlib.Path(tempfile.mkdtemp(prefix="reviewer-test-"))
    atexit.register(shutil.rmtree, repo, ignore_errors=True)
    git(repo, "init", "-q", "-b", branch)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo, "README.md", "test repo\n")
    commit(repo, "initial")
    return repo


def write(repo, rel_path, text):
    path = pathlib.Path(repo) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def run_cli(repo, *args):
    """Run reviewer.main in-process; returns (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = reviewer.main([*args, "--repo", str(repo)])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, out.getvalue(), err.getvalue()
