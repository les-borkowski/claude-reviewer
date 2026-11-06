"""Prepare: static tool hints, the shared context pack, and intent."""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from reviewer_log import git
from reviewer_scope import default_branch

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

TOOL_TIMEOUT = 120
PLAN_CAP = 20000
MAX_CALLERS = 20
ALL_LANGS = {"python", "java", "typescript-react"}
EXTS = {"python": ["*.py"], "java": ["*.java"], "typescript-react": ["*.ts", "*.tsx"]}
_MODS = r"(?:(?:public|protected|private|static|final|abstract|synchronized|default|sealed)\s+)"
DEFS = {
    "python": [r"^(\s*)(?:async\s+)?def\s+(\w+)", r"^(\s*)class\s+(\w+)"],
    "typescript-react": [
        r"^(\s*)(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)",
        r"^(\s*)(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\(|\w+\s*=>|function)",
        r"^(\s*)(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)",
        r"^(\s*)export\s+(?:interface|type|enum)\s+(\w+)",
    ],
    "java": [rf"^(\s*){_MODS}*(?:class|interface|record|enum)\s+(\w+)",
             rf"^(\s*){_MODS}+[\w<>\[\],.? ]+\s+(\w+)\s*\("],
}
DEF_RES = {lang: [re.compile(p) for p in pats] for lang, pats in DEFS.items()}


# --- static tools ---------------------------------------------------------

class ToolFailed(Exception):
    pass


def _rel(repo, name):
    p = Path(name)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(Path(repo).resolve()).as_posix()
        except ValueError:
            return name
    return p.as_posix()


def _run(exe, args, repo):
    try:
        return subprocess.run([exe, *args], cwd=repo, capture_output=True, text=True,
                              timeout=TOOL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ToolFailed(str(e)) from None


def _json_output(proc, text=None):
    """Parsed JSON output; empty result for a clean exit with nothing parsable."""
    try:
        return json.loads(proc.stdout if text is None else text)
    except (ValueError, TypeError):
        if proc.returncode != 0:
            raise ToolFailed(proc.stderr[-500:]) from None
        return None


def _vulture(exe, repo, files):
    proc = _run(exe, [*files, "--min-confidence", "80"], repo)
    found = re.findall(r"^(.+?):(\d+): (.+)$", proc.stdout, re.M)
    if not found and proc.returncode not in (0, 3):  # 3 = dead code found
        raise ToolFailed(proc.stderr[-500:])
    return [{"tool": "vulture", "rule": "CM-01", "path": _rel(repo, p), "lines": [int(n), int(n)],
             "message": msg} for p, n, msg in found], []


def _jscpd(exe, repo, files):
    with tempfile.TemporaryDirectory() as out:
        proc = _run(exe, ["--silent", "--reporters", "json", "--output", out, *files], repo)
        report = Path(out) / "jscpd-report.json"
        data = _json_output(proc, report.read_text() if report.exists() else None) or {}
    hints = []
    for dup in data.get("duplicates", []):
        first, second = dup.get("firstFile", {}), dup.get("secondFile", {})
        for this, other in ((first, second), (second, first)):
            hints.append({"tool": "jscpd", "rule": "CM-09", "path": _rel(repo, this.get("name", "")),
                          "lines": [this.get("start", 0), this.get("end", 0)],
                          "message": f"duplicate of {_rel(repo, other.get('name', ''))}:"
                                     f"{other.get('start')}-{other.get('end')}"})
    return hints, []


def _knip(exe, repo, files):
    data = _json_output(_run(exe, ["--reporter", "json"], repo)) or {}
    hints = [{"tool": "knip", "rule": "CM-01", "path": _rel(repo, f), "lines": None,
              "message": "unused file"} for f in data.get("files", [])]  # None: whole file
    for issue in data.get("issues", []):
        for kind in ("exports", "types"):
            for item in issue.get(kind, []):
                line = item.get("line", 1)
                hints.append({"tool": "knip", "rule": "CM-01", "path": _rel(repo, issue.get("file", "")),
                              "lines": [line, line], "message": f"unused {kind[:-1]} {item.get('name')}"})
    return hints, []


def _ruff(exe, repo, files):
    data = _json_output(_run(exe, ["check", "--output-format", "json", *files], repo)) or []
    return [], [{"tool": "ruff", "path": _rel(repo, d["filename"]), "line": d["location"]["row"],
                 "code": d.get("code")} for d in data]


def _eslint(exe, repo, files):
    data = _json_output(_run(exe, ["-f", "json", *files], repo)) or []
    return [], [{"tool": "eslint", "path": _rel(repo, f["filePath"]), "line": m.get("line", 0),
                 "code": m.get("ruleId")} for f in data for m in f.get("messages", [])]


# Whole-repo tools: unused-code and duplicate checks need the code around the change.
WHOLE_REPO = {"vulture", "jscpd"}
# name: (languages, ecosystem, adapter)
TOOLS = {
    "vulture": ({"python"}, "python", _vulture),
    "jscpd": (ALL_LANGS, "node", _jscpd),
    "knip": ({"typescript-react"}, "node", _knip),
    "ruff": ({"python"}, "python", _ruff),
    "eslint": ({"typescript-react"}, "node", _eslint),
}
LOCAL_BIN = {"node": "node_modules/.bin", "python": ".venv/bin"}


def _package_json(repo):
    try:
        data = json.loads((Path(repo) / "package.json").read_text())
    except (OSError, ValueError):
        return {}
    return {**data.get("dependencies", {}), **data.get("devDependencies", {})}


def _executable(repo, name, ecosystem):
    """Path to the tool if usable: Python tools from PATH or the repo's .venv; Node
    tools only when the repo's package.json lists them (PATH or node_modules/.bin)."""
    if ecosystem == "node" and name not in _package_json(repo):
        return None
    local = Path(repo) / LOCAL_BIN[ecosystem] / name
    return str(local) if local.exists() else shutil.which(name)


def _source_files(repo, langs):
    """Tracked and untracked, not ignored, source files of these languages."""
    patterns = [p for lang in langs for p in EXTS[lang]]
    return git(repo, "ls-files", "-co", "--exclude-standard", "--", *patterns).splitlines()


def _ranges(scope):
    return {f["path"]: f["ranges"] for f in scope["files"]}


def _in_ranges(ranges, start, end):
    return any(s <= end and start <= e for s, e in ranges)


def run_tools(repo, scope):
    # shortcut: no Java adapters in v1 (PMD/CPD need build config), add when a Java repo is reviewed.
    repo = Path(repo)
    langs = {f["lang"] for f in scope["files"]}
    ranges = _ranges(scope)
    status, hints, lint = {}, [], []
    for name, (tool_langs, ecosystem, adapter) in TOOLS.items():
        files = [f["path"] for f in scope["files"] if f["lang"] in tool_langs]
        if not files:
            continue
        if name in WHOLE_REPO:  # hints are still filtered to changed lines below
            files = _source_files(repo, tool_langs & langs)
        exe = _executable(repo, name, ecosystem)
        if exe is None:
            status[name] = "missing"
            continue
        try:
            tool_hints, tool_lint = adapter(exe, repo, files)
        except (ToolFailed, KeyError, TypeError, AttributeError):
            status[name] = "failed"
            continue
        status[name] = "ran"
        for h in tool_hints:
            changed = ranges.get(h["path"], [])
            if h["lines"] is None and changed:  # whole-file hint: the changed span
                h["lines"] = [changed[0][0], changed[-1][1]]
            if h["lines"] and _in_ranges(changed, *h["lines"]):
                hints.append(h)
        lint += [x for x in tool_lint if _in_ranges(ranges.get(x["path"], []), x["line"], x["line"])]
    return {"tools": status, "hints": hints, "lint": lint}


# --- context pack ---------------------------------------------------------

def _definitions(text, lang, top_level_only=False):
    """[(name, line)] for definitions in text."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for rx in DEF_RES[lang]:
            m = rx.match(line)
            if m and not (top_level_only and lang != "java" and m.group(1)):
                found.append((m.group(2), n))
                break
    return found


def _callers(repo, name, path, line):
    out = git(repo, "grep", "-n", "-w", "-F", "--untracked", "-I", "-e", name, check=False)
    callers = []
    for hit in out.splitlines():
        hit_path, hit_line, text = hit.split(":", 2)
        if (hit_path, int(hit_line)) != (path, line):
            callers.append({"path": hit_path, "line": int(hit_line), "text": text.strip()[:200]})
    return callers[:MAX_CALLERS]


def _index(repo, langs):
    paths = _source_files(repo, langs)
    index = []
    for path in paths:
        lang = next(l for l in langs if any(Path(path).match(p) for p in EXTS[l]))
        try:
            text = (Path(repo) / path).read_text(errors="replace")
        except OSError:
            continue
        index += [{"name": n, "path": path, "line": ln} for n, ln in _definitions(text, lang, True)]
    return index


def _req_name(spec):
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return m.group(1) if m else None


def _pyproject_specs(text):
    if tomllib is None:
        # shortcut: Python 3.10 has no tomllib; pull quoted strings out of the
        # `dependencies = [...]` arrays and [dependency-groups] arrays by regex.
        groups = re.search(r"^\[dependency-groups\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
        # An array ends at a `]` closing its line, not at the `]` of an extra
        # like "uvicorn[standard]".
        arrays = re.findall(r"^dependencies\s*=\s*\[(.*?)\]\s*$", text, re.M | re.S)
        arrays += re.findall(r"=\s*\[(.*?)\]\s*$", groups.group(1), re.M | re.S) if groups else []
        return [s for a in arrays for s in re.findall(r'"([^"]+)"', re.sub(r"\{.*?\}", "", a))]
    data = tomllib.loads(text)
    specs = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
        specs += [s for s in group if isinstance(s, str)]
    return specs


def _dependencies(repo):
    # shortcut: root manifests only; monorepo sub-packages are not read.
    repo = Path(repo)
    specs = []
    if (repo / "pyproject.toml").exists():
        try:
            specs += _pyproject_specs((repo / "pyproject.toml").read_text())
        except ValueError:
            pass
    for req in repo.glob("requirements*.txt"):
        specs += [l for l in req.read_text().splitlines() if l.strip() and l.strip()[0] not in "#-"]
    names = {_req_name(s) for s in specs} | set(_package_json(repo))
    if (repo / "pom.xml").exists():
        names |= set(re.findall(r"<artifactId>\s*([^<\s]+)\s*</artifactId>", (repo / "pom.xml").read_text()))
    return sorted(n for n in names if n)


def _size(pack):
    return len(json.dumps(pack))


def _fit_list(pack, key, budget):
    """Shorten pack[key] to the longest prefix that fits, by binary search."""
    items, lo, hi = pack[key], 0, len(pack[key])
    while lo < hi:
        mid = (lo + hi + 1) // 2
        pack[key] = items[:mid]
        lo, hi = (mid, hi) if _size(pack) <= budget else (lo, mid - 1)
    pack[key] = items[:lo]


def _truncate(pack, budget):
    if _size(pack) <= budget:
        return pack
    pack["truncated"] = True
    callers = {id(s): s["callers"] for s in pack["symbols"]}
    for cap in range(MAX_CALLERS - 1, -1, -1):  # callers first, evenly across symbols
        for s in pack["symbols"]:
            s["callers"] = callers[id(s)][:cap]
        if _size(pack) <= budget:
            return pack
    for key in ("index", "symbols", "dependencies"):
        _fit_list(pack, key, budget)
        if _size(pack) <= budget:
            break
    return pack


def build_context(repo, scope, budget_chars=60000):
    repo = Path(repo)
    symbols = []
    for f in scope["files"]:
        text = (repo / f["path"]).read_text(errors="replace")
        for name, line in _definitions(text, f["lang"]):
            if _in_ranges(f["ranges"], line, line):
                symbols.append({"name": name, "path": f["path"], "line": line,
                                "callers": _callers(repo, name, f["path"], line)})
    langs = sorted({f["lang"] for f in scope["files"]})
    pack = {"symbols": symbols, "index": _index(repo, langs) if langs else [],
            "dependencies": _dependencies(repo), "truncated": False}
    return _truncate(pack, budget_chars)


# --- intent ---------------------------------------------------------------

def collect_intent(repo, scope):
    repo = Path(repo)
    branch = scope["branch"]
    log = git(repo, "log", "--format=%B%x00", f"{scope['base']}..HEAD", check=False)
    commits = [m.strip() for m in log.split("\0") if m.strip()]
    slug = branch.rsplit("/", 1)[-1]
    default = default_branch(repo)
    candidates = []
    # On the default branch (or detached) the name says nothing about the task.
    if branch != "HEAD" and (default is None or branch != default.removeprefix("origin/")):
        candidates = [p for pattern in ("docs/**/*plan*.md", "docs/superpowers/plans/*.md")
                      for p in repo.glob(pattern) if slug in p.name]
        candidates += repo.glob(f".scratch/{slug}/**/*.md")
    plans, seen = [], set()
    for p in sorted(candidates):
        rel = p.relative_to(repo).as_posix()
        if rel not in seen and p.is_file():
            seen.add(rel)
            plans.append({"path": rel, "text": p.read_text(errors="replace")[:PLAN_CAP]})
    sources = [name for name, found in (("commits", commits), ("plan", plans)) if found]
    return {"sources": sources, "branch": branch, "commits": commits, "plans": plans}
