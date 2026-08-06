"""validate_repo.py — `/validate` check 7, repo hygiene. Gate 1.

No tracked files under `temp_data/`, `content-staging/`, or any `.env` other
than `.env.example`.

**Checks `git ls-files`, not just `git status`.** A force-added file
(`git add -f`) shows as clean in `status` forever, because once it is tracked
git stops caring what `.gitignore` says. `status` would report the tree clean
while a secret sat in the index. `ls-files` is the one that tells the truth.

This is the cheap sibling of the Gate 7 deploy guard. Check 7 asserts the
invariant over the repo as it stands; check 15 exercises the guard code against
a deliberately staged illegal file. Both are needed, and the reference had only
the manual version of either.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import ROOT  # noqa: E402

#: Paths that must never be tracked. TRD.md §2.4's volume-state list.
FORBIDDEN_PREFIXES = ("temp_data/", "content-staging/")

#: The one `.env*` file that is tracked.
ALLOWED_ENV = ".env.example"


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def offending(paths: list[str]) -> list[str]:
    """The real check, factored out so the self-test can drive it directly."""
    errors: list[str] = []
    for path in paths:
        for prefix in FORBIDDEN_PREFIXES:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                errors.append(f"tracked file under {prefix}: {path}")
        name = Path(path).name
        if name.startswith(".env") and name != ALLOWED_ENV:
            errors.append(f"tracked env file: {path} (only {ALLOWED_ENV} is tracked)")
    return errors


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    clean = [
        "site/src/config.ts",
        "admin/config.py",
        ".env.example",
        "data/ownership.json",
        "site/public/fonts/ibm-plex-mono-400.woff2",
    ]
    if offending(clean):
        errors.append(f"selftest: clean file list rejected: {offending(clean)}")

    dirty_cases = [
        (["temp_data/harvest_queue.json"], "temp_data"),
        (["temp_data/images/x.jpg"], "temp_data"),
        (["content-staging/_staging/foo.mdx"], "content-staging"),
        ([".env"], "env"),
        ([".env.local"], "env"),
        (["admin/.env.production"], "env"),
    ]
    for paths, label in dirty_cases:
        if not offending(paths):
            errors.append(f"selftest: '{label}' fixture {paths} was NOT caught")

    return errors


def check_7_repo_hygiene() -> list[str]:
    return offending(tracked_files())


def main() -> int:
    errors = _selftest() + check_7_repo_hygiene()
    if errors:
        print(f"VALIDATE 7 FAIL — {len(errors)} error(s)")
        for message in errors:
            print(f"  {message}")
        return 1
    print(f"VALIDATE 7 PASS — selftest ok; {len(tracked_files())} tracked files, 0 illegal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
