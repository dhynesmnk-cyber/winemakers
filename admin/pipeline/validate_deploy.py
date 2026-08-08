"""validate_deploy.py — `/validate` check 15, the deploy-guard self-test. Gate 7.

**This is a test, not an assertion.** Check 7 already asserts the invariant over
the repository as it stands: nothing illegal is tracked. Check 15 asks the
different and harder question, which is whether the *guard would refuse* if
something illegal were tracked. Those are not the same claim, and only one of
them survives a refactor of `deploy.py`.

That distinction is the reason this module exists. The reference implementation
left its deploy guard covered by a manual gate exit, and CLAUDE.md Gate 7 calls
that the one clear gap in it. A guard nobody has ever seen refuse anything is a
guard nobody has tested.

── How the fixtures work ────────────────────────────────────────────────────

Each case builds a throwaway git repository in a temp directory: a bare
`origin.git` plus a clone of it, so `git pull --ff-only` and `git push` behave
as they do in production rather than failing for want of a remote. The tree
mirrors the shape of the real one closely enough for `ALLOWED_PREFIXES` to
mean something: a published MDX, the SQLite file, a source file, `.env.example`
and a `site/package.json` whose `build` script we choose.

`deploy.py` takes `root` and `site_dir` as parameters, so these fixtures drive
**the same functions the admin calls**. Nothing is reimplemented here and no
module global is monkeypatched, with one exception: `_poll_netlify` is stubbed,
because it is a network call to a third party and the fixture's commit will
never appear in anyone's Netlify account. Everything check 15 is about happens
before the poll.

The central case is the one CLAUDE.md names. A `temp_data/` file is force-added
**and committed**, so `git status` reports a clean tree and only `git ls-files`
knows it is there. That is exactly the trap the guard exists for, and a guard
written against `git status` would sail past it.

Runs fully offline.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import ROOT  # noqa: E402
from admin.pipeline import deploy  # noqa: E402

#: The illegal file at the centre of the check. CLAUDE.md Gate 7: "the guard
#: demonstrably refuses a deliberately staged tracked `temp_data/` file as an
#: automated self-test, not a manual check".
ILLEGAL_FILE = "temp_data/harvest_queue.json"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True
    )
    if result.returncode != 0 and args[0] not in ("status", "ls-files"):
        raise RuntimeError(f"fixture git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commits(root: Path) -> int:
    return int(_git(root, "rev-list", "--count", "HEAD").stdout.strip() or 0)


def _build_fixture(tmp: Path, build_exit: int = 0) -> Path:
    """A bare origin plus a clone of it, holding a plausible tree."""
    origin = tmp / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        capture_output=True,
        text=True,
        check=True,
    )
    work = tmp / "work"
    subprocess.run(
        ["git", "clone", str(origin), str(work)], capture_output=True, text=True, check=True
    )

    _git(work, "config", "user.email", "validate@example.invalid")
    _git(work, "config", "user.name", "check 15")
    _git(work, "config", "commit.gpgsign", "false")

    _write(work / ".gitignore", "temp_data/\ncontent-staging/\n.env\n.env.*\n!.env.example\n")
    _write(
        work / "site/src/content/producers/_published/example-wines.mdx",
        "---\nname: Example Wines\n---\n\nA documented entry.\n",
    )
    _write(work / "data/directory.db", "not really sqlite\n")
    _write(work / "data/ownership.json", '{"updated": "2026-08-08", "records": []}\n')
    _write(work / "admin/app.py", "# source, never part of a publish commit\n")
    _write(work / ".env.example", "SITE_URL=\n")
    # The pre-push build gate runs `npm run build` in this directory. The script
    # is the whole point of the fixture: it decides whether the gate passes.
    _write(
        work / "site/package.json",
        json.dumps(
            {"name": "fixture", "private": True, "scripts": {"build": f"exit {build_exit}"}},
            indent=2,
        )
        + "\n",
    )

    _git(work, "add", "-A")
    _git(work, "commit", "-m", "fixture tree")
    _git(work, "push", "-u", "origin", "main")
    return work


def _publish_change(work: Path) -> None:
    """Something legitimate to deploy, so a refusal cannot be mistaken for
    'nothing to do'."""
    _write(
        work / "site/src/content/producers/_published/example-wines.mdx",
        "---\nname: Example Wines\n---\n\nA documented entry, edited.\n",
    )


@contextlib.contextmanager
def _stubbed_netlify_poll():
    """The one patched boundary. See the module docstring."""
    original = deploy._poll_netlify

    def _stub(commit_sha: str, urls: set[str]):
        yield deploy.LogLine("00:00:00", "info", f"netlify poll stubbed, sha {commit_sha[:7]}")

    deploy._poll_netlify = _stub
    try:
        yield
    finally:
        deploy._poll_netlify = original


def _deploy(work: Path, message: str = "") -> list[deploy.LogLine]:
    with _stubbed_netlify_poll():
        return list(deploy.run_deploy(message, root=work, site_dir=work / "site"))


def _errors_in(lines: list[deploy.LogLine]) -> list[str]:
    return [line.text for line in lines if line.level == "error"]


def _mentions(lines: list[deploy.LogLine], needle: str) -> bool:
    return any(needle in line.text for line in lines)


# =============================================================================
# The cases
# =============================================================================


def _case_clean_tree_passes(tmp: Path) -> list[str]:
    """A clean tree with a real content change deploys, and the guard is silent."""
    errors: list[str] = []
    work = _build_fixture(tmp)
    _publish_change(work)
    _write(work / "data/directory.db", "not really sqlite, rebuilt\n")

    violations = deploy.guard_violations(root=work)
    if violations:
        errors.append(f"clean tree: guard reported {violations} on a clean fixture")

    preview = deploy.build_preview(root=work)
    if preview.blocked:
        errors.append(
            f"clean tree: preview blocked. unexpected={preview.unexpected} "
            f"guard={preview.guard_violations}"
        )
    paths = preview.paths
    expected = [
        "data/directory.db",
        "site/src/content/producers/_published/example-wines.mdx",
    ]
    if paths != expected:
        errors.append(f"clean tree: preview files were {paths}, expected {expected}")
    changes = {item.path: item.change for item in preview.files}
    if changes.get("data/directory.db") != "edited":
        errors.append(f"clean tree: change type was {changes.get('data/directory.db')!r}, expected 'edited'")
    if "example-wines" not in preview.commit_message:
        errors.append(f"clean tree: commit message did not name the slug: {preview.commit_message!r}")
    return errors


def _case_tracked_temp_data_refused(tmp: Path) -> list[str]:
    """THE case. A tracked file under a gitignored path, invisible to git status."""
    errors: list[str] = []
    work = _build_fixture(tmp)

    _write(work / ILLEGAL_FILE, '{"queue": ["https://example.invalid/"]}\n')
    _git(work, "add", "-f", "--", ILLEGAL_FILE)
    _git(work, "commit", "-m", "force-add the illegal file")

    # The trap, stated as an assertion: status is clean, ls-files is not.
    status = _git(work, "status", "--porcelain=v1").stdout.strip()
    if status:
        errors.append(f"fixture: expected a clean git status, got {status!r}")
    violations = deploy.guard_violations(root=work)
    if ILLEGAL_FILE not in violations:
        errors.append(
            f"THE GUARD DID NOT CATCH {ILLEGAL_FILE}. guard_violations returned {violations}"
        )

    _publish_change(work)
    before = _commits(work)
    lines = _deploy(work)
    after = _commits(work)

    if not _mentions(lines, ILLEGAL_FILE):
        errors.append(f"deploy did not name {ILLEGAL_FILE} in its output: {[l.text for l in lines]}")
    if not _errors_in(lines):
        errors.append("deploy produced no error line against a tracked temp_data file")
    if after != before:
        errors.append(f"DEPLOY COMMITTED ANYWAY: commit count went {before} to {after}")
    if _mentions(lines, "push ok"):
        errors.append("DEPLOY PUSHED ANYWAY")
    return errors


def _case_tracked_env_refused(tmp: Path) -> list[str]:
    """`.env` is refused; `.env.example`, already in the fixture, is not."""
    errors: list[str] = []
    work = _build_fixture(tmp)

    if deploy.guard_violations(root=work):
        errors.append(".env.example was treated as a violation, and it is the one tracked env file")

    _write(work / ".env", "ANTHROPIC_API_KEY=would-be-a-real-secret\n")
    _git(work, "add", "-f", "--", ".env")
    _git(work, "commit", "-m", "force-add .env")

    violations = deploy.guard_violations(root=work)
    if ".env" not in violations:
        errors.append(f"the guard did not catch a tracked .env: {violations}")
    if ".env.example" in violations:
        errors.append("the guard caught .env.example, which is tracked deliberately")
    return errors


def _case_unexpected_path_refused(tmp: Path) -> list[str]:
    """A changed source file is outside the publish set and stops the deploy."""
    errors: list[str] = []
    work = _build_fixture(tmp)
    _publish_change(work)
    _write(work / "admin/app.py", "# source, edited\n")

    before = _commits(work)
    lines = _deploy(work)
    if not _mentions(lines, "admin/app.py"):
        errors.append("deploy did not name the unexpected path in its output")
    if not _mentions(lines, "outside the publish set"):
        errors.append("deploy refused without saying why")
    if _commits(work) != before:
        errors.append("deploy committed despite a path outside the publish set")
    return errors


def _case_build_failure_blocks_push(tmp: Path) -> list[str]:
    """CLAUDE.md Gate 7: `npm run build` failure blocks the push."""
    errors: list[str] = []
    work = _build_fixture(tmp, build_exit=1)
    _publish_change(work)

    before = _commits(work)
    lines = _deploy(work)
    if not _errors_in(lines):
        errors.append("a failing site build produced no error line")
    if not _mentions(lines, "site build failed"):
        errors.append(f"the refusal did not name the build: {[l.text for l in lines]}")
    if _commits(work) != before:
        errors.append("DEPLOY COMMITTED DESPITE A FAILING BUILD")
    if _mentions(lines, "push ok"):
        errors.append("DEPLOY PUSHED DESPITE A FAILING BUILD")
    return errors


def _case_happy_path_pushes(tmp: Path) -> list[str]:
    """The positive control: a passing build commits and pushes, allowed paths only.

    Without this, every case above could pass because the deploy never works at
    all, and a permanently broken deploy would score a clean check 15.
    """
    errors: list[str] = []
    work = _build_fixture(tmp, build_exit=0)
    _publish_change(work)
    _write(work / "data/directory.db", "not really sqlite, rebuilt\n")

    before = _commits(work)
    lines = _deploy(work, "Publish: example-wines")
    if _errors_in(lines):
        errors.append(f"the happy path produced errors: {_errors_in(lines)}")
    if _commits(work) != before + 1:
        errors.append(f"no commit was made: count stayed at {before}")
        return errors
    if not _mentions(lines, "push ok"):
        errors.append("the deploy did not report a successful push")

    committed = sorted(
        _git(work, "show", "--name-only", "--format=", "HEAD").stdout.split()
    )
    expected = [
        "data/directory.db",
        "site/src/content/producers/_published/example-wines.mdx",
    ]
    if committed != expected:
        errors.append(f"the commit touched {committed}, expected {expected}")
    for path in committed:
        if not deploy._is_allowed(path):
            errors.append(f"the commit carried a path outside the allow-list: {path}")

    # It reached the bare origin, which is what "push" has to mean.
    remote = _git(work, "log", "--oneline", "origin/main", "-1").stdout.strip()
    if "Publish: example-wines" not in remote:
        errors.append(f"the commit did not reach origin: origin/main is at {remote!r}")
    return errors


def _case_npm_missing_refuses() -> list[str]:
    """The 2026-08-08 divergence: no npm means refuse, never skip."""
    errors: list[str] = []
    try:
        list(deploy._site_build_gate(Path("/nonexistent")))
    except deploy.DeployRefused:
        return errors
    except Exception as exc:  # noqa: BLE001
        errors.append(f"npm-missing: expected DeployRefused, got {type(exc).__name__}: {exc}")
        return errors
    errors.append("npm-missing: the build gate did not refuse when npm was absent")
    return errors


# =============================================================================
# The check
# =============================================================================

#: Cases that need a fixture repository, run in a fresh temp directory each.
CASES = (
    ("clean tree passes", _case_clean_tree_passes),
    ("tracked temp_data file refused", _case_tracked_temp_data_refused),
    ("tracked .env refused", _case_tracked_env_refused),
    ("unexpected path refused", _case_unexpected_path_refused),
)

#: Cases that additionally need `npm` on the path.
NPM_CASES = (
    ("build failure blocks the push", _case_build_failure_blocks_push),
    ("happy path commits and pushes", _case_happy_path_pushes),
)


def _selftest() -> tuple[list[str], list[str]]:
    """Must catch a corrupted fixture and pass a clean one.

    Returns (errors, notes). Notes report what could not be exercised here, so a
    skipped case is visible rather than counted as a pass.
    """
    errors: list[str] = []
    notes: list[str] = []

    cases = list(CASES)
    if shutil.which("npm") is None:
        notes.append(
            "npm is not on the path, so the build-gate cases did not run. "
            "The gate's refusing branch was exercised instead."
        )
        errors += [f"npm-missing: {message}" for message in _case_npm_missing_refuses()]
    else:
        cases += list(NPM_CASES)

    for name, case in cases:
        with tempfile.TemporaryDirectory(prefix="check15-") as raw:
            try:
                errors += [f"{name}: {message}" for message in case(Path(raw))]
            except Exception as exc:  # noqa: BLE001 - a crashing case is a failing case
                errors.append(f"{name}: raised {type(exc).__name__}: {exc}")
    return errors, notes


def check_15_deploy_guard() -> list[str]:
    """The live repository's own guard state, through the deploy's code path.

    Check 7 covers the same ground from `validate_repo`'s side. This runs the
    function the deploy actually calls, which matters because the two do not
    agree in every case: check 7 allows any file named `.env.example` at any
    depth, and the guard allows only the one at the root.
    """
    return [
        f"tracked file under a gitignored path: {path}"
        for path in deploy.guard_violations(root=ROOT)
    ]


def main() -> int:
    errors, notes = _selftest()
    errors += check_15_deploy_guard()
    for note in notes:
        print(f"  note: {note}")
    if errors:
        print(f"VALIDATE 15 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    exercised = len(CASES) + (0 if shutil.which("npm") is None else len(NPM_CASES))
    print(
        f"VALIDATE 15 PASS — {exercised} fixture case(s) exercised the guard; "
        f"live repo clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
