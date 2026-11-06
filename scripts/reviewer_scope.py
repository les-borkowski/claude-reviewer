"""Scope: which files and line ranges a review covers, from which base."""
import fnmatch
import re
import subprocess
from pathlib import Path

from reviewer_log import git, hunks, last_review

NO_BASE = "no base found; pass a ref: /reviewer:review <ref>"
LARGE_DIFF = 400
LANGS = {".py": "python", ".java": "java", ".ts": "typescript-react", ".tsx": "typescript-react"}
SKIP_GLOBS = ["*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock",
              "poetry.lock", "*/migrations/*", "*/alembic/versions/*", "*/vendor/*",
              "*/node_modules/*", "*/generated/*", "*.min.js", "*.d.ts"]
KEEP = re.compile(r"reviewer:\s*keep\s+([A-Z]{2}-\d{2})\s+(\S.*)")
COMMENT_CLOSE = re.compile(r"\s*(\*/\}?|-->)\s*$")


class NoBase(Exception):
    pass


def _ok(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True).returncode == 0


def _sha(repo, rev):
    return git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()


def default_branch(repo):
    target = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False).strip()
    candidates = [target.removeprefix("refs/remotes/")] if target else []
    for name in [*candidates, "main", "master"]:
        if _ok(repo, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"):
            return name
    return None


def _base(repo, branch, ref, full):
    if ref:
        try:
            return _sha(repo, ref), "ref"
        except subprocess.CalledProcessError:
            raise NoBase(f"unknown ref: {ref}") from None
    last = None if full else last_review(repo, branch)
    if last and last.get("head") and _ok(repo, "merge-base", "--is-ancestor", last["head"], "HEAD"):
        return last["head"], "last_review"
    default = default_branch(repo)
    if default is None:
        raise NoBase(NO_BASE)
    if branch == default.removeprefix("origin/"):
        return _sha(repo, "HEAD"), "merge_base"
    return git(repo, "merge-base", "HEAD", default).strip(), "merge_base"


def _skip_reason(repo, path):
    if any(fnmatch.fnmatchcase("/" + path, g if "/" in g else "*/" + g) for g in SKIP_GLOBS):
        return "skip"
    if Path(path).suffix not in LANGS:
        return "unsupported"
    with open(Path(repo) / path, "rb") as f:
        if b"\0" in f.read(8000):  # git's own binary heuristic
            return "binary"
    return None


def _new_ranges(diff_text):
    """{new path: [[start, end], ...]} from a --unified=0 diff."""
    ranges, path = {}, None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = None if line == "+++ /dev/null" else line[6:].rstrip("\t")
            if path:
                ranges.setdefault(path, [])
        elif line.startswith("@@") and path:
            for _, _, start, count in hunks(line):
                if count:
                    ranges[path].append([start, start + count - 1])
    return ranges


def _name_status(repo, base):
    """[(status letter, new-or-only path)] from `git diff --name-status -z -M`."""
    tokens = git(repo, "diff", "--name-status", "-z", "-M", base).split("\0")
    entries, i = [], 0
    while i < len(tokens) - 1:
        status = tokens[i]
        step = 3 if status[:1] in "RC" else 2
        entries.append((status[:1], tokens[i + step - 1]))
        i += step
    return entries


def _keep_markers(repo, path):
    markers = []
    text = (Path(repo) / path).read_text(errors="replace")
    for n, line in enumerate(text.splitlines(), 1):
        m = KEEP.search(line)
        reason = m and COMMENT_CLOSE.sub("", m.group(2)).strip()
        if reason:
            markers.append({"path": path, "line": n, "rule": m.group(1), "reason": reason})
    return markers


def compute_scope(repo, ref=None, full=False):
    repo = Path(repo)
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    base, base_kind = _base(repo, branch, ref, full)
    diff = git(repo, "-c", "core.quotePath=false", "diff", "--unified=0", "-M",
               "--no-color", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/", base)
    status = _name_status(repo, base)
    deleted = [path for letter, path in status if letter == "D"]
    ranges = _new_ranges(diff)
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for path in filter(None, untracked):
        count = len((repo / path).read_bytes().splitlines())
        ranges[path] = [[1, count]] if count else []

    files, skipped, markers = [], list(deleted), []
    for path, path_ranges in ranges.items():
        if _skip_reason(repo, path):
            skipped.append(path)
        elif path_ranges:
            files.append({"path": path, "lang": LANGS[Path(path).suffix], "ranges": path_ranges})
            markers += _keep_markers(repo, path)
    # Binary files have no `+++` line in a text diff; list them from name-status.
    changed = {path for letter, path in status if letter in "AMT"}
    skipped += sorted(p for p in changed - ranges.keys() if p not in skipped)
    changed_lines = sum(e - s + 1 for f in files for s, e in f["ranges"])
    return {"base": base, "base_kind": base_kind, "head": _sha(repo, "HEAD"), "branch": branch,
            "changed_lines": changed_lines, "large": changed_lines > LARGE_DIFF,
            "files": files, "skipped": skipped, "keep_markers": markers}
