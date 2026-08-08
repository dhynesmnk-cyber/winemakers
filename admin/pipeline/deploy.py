"""deploy.py — the deploy strip's backend. Gate 7. TRD.md §6.5, UX.md §1.6.

Ported from the reference's `deploy.py` unchanged in shape: a diff preview
showing only legal paths, a tracked-file guard reading `git ls-files`, a
pre-push `npm run build` gate, the streamed add/commit/push, a Netlify build
poll and an IndexNow ping. One lock, so no two paths can race a push.

── The two refusals, and why they are separate ──────────────────────────────

`unexpected` is a changed file outside `ALLOWED_PREFIXES`: an edit to source, a
stray note, a rebuilt artefact nobody meant to publish. It is visible in
`git status` and the reviewer can see it.

`guard_violations` is a **tracked** file under a gitignored path. It is not
visible in `git status`: once a file is tracked, git stops consulting
`.gitignore`, so a `git add -f temp_data/...` shows a clean tree forever. That
is why the guard reads `git ls-files` (the index) rather than `git status`, and
why `/validate` check 15 exercises this function against a deliberately staged
file rather than restating the invariant.

Both refuse the deploy (UX.md §1.5 row 22).

── Deliberate non-ports from the reference ──────────────────────────────────

`run_auto_deploy()` is **not carried**. The reference's Stripe claim webhook was
the one path in that system where a write reached the live site with no human
clicking Deploy; this project does not carry the claim flow (TRD.md §8), so the
invariant holds that every write stops at "updated on disk" until a human clicks
Deploy (TRD.md §2.4). `DEPLOY_LOCK` is still here: TRD.md §6.5 requires one lock
so no two paths can race a push, and the admin can serve two browser tabs.

`_regenerate_og_cards()` is not carried. There are no generated share cards in
this build.

── One divergence, 2026-08-08 (Gate 7) ─────────────────────────────────────

The reference **skips** the pre-push build gate with a warning when `npm` is not
on the path. This build **refuses** instead. CLAUDE.md Gate 7's done-condition
is that a `npm run build` failure blocks the push, and a gate an environment
quirk can switch off is not a gate. The Docker base image installs Node 20
(TRD.md §2.4), so the refusing branch should never fire in the container; when
it does fire, it means the pre-push check could not be made and the honest
answer is to stop rather than to push content nothing verified.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import httpx

from admin.config import (
    INDEXNOW_KEY,
    NETLIFY_AUTH_TOKEN,
    NETLIFY_SITE_ID,
    ROOT,
    SITE_DIR,
    SITE_URL,
)

#: TRD.md §6.5: one deploy lock, so no two paths can race a push. Held by the
#: admin's deploy route for the whole run, released in a `finally`.
DEPLOY_LOCK = threading.Lock()

#: The only paths a deploy may touch (TRD.md §6.5, UX.md §1.6). Everything else
#: in this repository is source, working state or documentation, and none of it
#: belongs in a publish commit.
ALLOWED_PREFIXES = (
    "site/src/content/producers/_published/",
    "site/public/images/",
    "data/directory.db",
    "data/ownership.json",
    "site/src/data/producers.json",
    "site/src/data/forewords.json",
    "site/src/content/blog/_published/",
    "site/public/blog-images/",
    "data/factchecks/",
)

#: Pathspecs that must never appear in `git ls-files`. TRD.md §2.4's volume-state
#: list, as git pathspecs rather than as the prefixes check 7 matches on.
GUARD_PATHSPECS = ("temp_data", "content-staging", ".env", ".env.*")

#: The one `.env*` file that is tracked, per `.gitignore`'s `!.env.example`.
#: Matched as a whole path, not by filename: git's `!.env.example` negation
#: applies at any depth, so a `admin/.env.example` holding real values would be
#: committable and would read as documentation. `/validate` check 7 matches on
#: the filename and would let that through; the deploy is the fail-closed side
#: of the pair and refuses it.
GUARD_ALLOWLIST = {".env.example"}

#: Words for a porcelain status code, because the reviewer reads this list and
#: `??` is not a word. UX.md §1.6: the diff preview carries the change type per
#: file.
CHANGE_WORDS = {
    "?": "new",
    "A": "new",
    "M": "edited",
    "D": "removed",
    "R": "renamed",
    "C": "copied",
    "T": "retyped",
    "U": "conflicted",
}

NETLIFY_POLL_INTERVAL_SECONDS = 10
NETLIFY_POLL_TIMEOUT_SECONDS = 360
BUILD_LOG_TAIL_LINES = 15
SITE_BUILD_TIMEOUT_SECONDS = 600

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


class DeployRefused(Exception):
    """Raised by a gate that stops the deploy. Carries the reason as its text."""


@dataclass
class LogLine:
    time: str
    level: str
    text: str


@dataclass
class DeployFile:
    path: str
    change: str


@dataclass
class DeployPreview:
    files: list[DeployFile] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    guard_violations: list[str] = field(default_factory=list)
    commit_message: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.guard_violations) or bool(self.unexpected)

    @property
    def paths(self) -> list[str]:
        return [item.path for item in self.files]


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _run_git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess:
    """Every git call in this module. `root` is a parameter so `/validate`
    check 15 can drive the real functions against a fixture repository rather
    than against a monkeypatched module global."""
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _is_allowed(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def guard_violations(root: Path = ROOT) -> list[str]:
    """Tracked files under a gitignored path. Reads the index, not the tree."""
    result = _run_git("ls-files", "--", *GUARD_PATHSPECS, root=root)
    return sorted(
        path for path in result.stdout.splitlines() if path and path not in GUARD_ALLOWLIST
    )


def _status_entries(root: Path = ROOT) -> list[tuple[str, str]]:
    result = _run_git("status", "--porcelain=v1", root=root)
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:  # rename entries read "old -> new"
            path = path.split(" -> ", 1)[1]
        entries.append((code, path))
    return entries


def _change_word(code: str) -> str:
    """The first non-space letter of the two-column porcelain code decides."""
    for column in code:
        if column != " " and column in CHANGE_WORDS:
            return CHANGE_WORDS[column]
    return "changed"


def _published_slugs_changed(entries: list[tuple[str, str]], prefix: str) -> list[str]:
    slugs = [
        Path(path).stem
        for _code, path in entries
        if path.startswith(prefix) and path.endswith(".mdx")
    ]
    return sorted(set(slugs))


def _auto_commit_message(producer_slugs: list[str], post_slugs: list[str]) -> str:
    """`Publish: jauma-wines, gentle-folk (+2 producers)` (UX.md §1.6)."""
    if not producer_slugs and not post_slugs:
        return "Publish: data refresh"
    parts: list[str] = []
    for slugs, noun in ((producer_slugs, "producer"), (post_slugs, "post")):
        if not slugs:
            continue
        shown = slugs[:2]
        rest = len(slugs) - len(shown)
        suffix = f" (+{rest} {noun}{'s' if rest != 1 else ''})" if rest > 0 else ""
        label = f"{', '.join(shown)}{suffix}"
        parts.append(label if noun == "producer" else f"blog: {label}")
    return f"Publish: {'; '.join(parts)}"


def build_preview(root: Path = ROOT) -> DeployPreview:
    entries = _status_entries(root)
    seen: dict[str, str] = {}
    for code, path in entries:
        if _is_allowed(path):
            seen.setdefault(path, _change_word(code))
    return DeployPreview(
        files=[DeployFile(path=path, change=seen[path]) for path in sorted(seen)],
        unexpected=sorted({path for _code, path in entries if not _is_allowed(path)}),
        guard_violations=guard_violations(root),
        commit_message=_auto_commit_message(
            _published_slugs_changed(entries, "site/src/content/producers/_published/"),
            _published_slugs_changed(entries, "site/src/content/blog/_published/"),
        ),
    )


def status_summary(root: Path = ROOT) -> dict:
    """The always-visible line: `4 files staged for publish, last deploy 2d ago`
    (UX.md §1.6), and its empty state."""
    preview = build_preview(root)
    last = _run_git("log", "-1", "--format=%cI", "--", *ALLOWED_PREFIXES, root=root)
    stamp = last.stdout.strip()
    last_deploy = "no deploy yet"
    if last.returncode == 0 and stamp:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).days
        last_deploy = "today" if days <= 0 else f"{days}d ago"

    count = len(preview.files)
    if count:
        summary = (
            f"{count} file{'s' if count != 1 else ''} staged for publish, "
            f"last deploy {last_deploy}"
        )
    else:
        summary = "Nothing to publish. Approve a draft first."

    return {
        "file_count": count,
        "last_deploy": last_deploy,
        "blocked": preview.blocked,
        "summary": summary,
        "commit_message": preview.commit_message,
        "running": DEPLOY_LOCK.locked(),
    }


def preview_payload(root: Path = ROOT) -> dict:
    """`build_preview` as JSON for the diff dialog."""
    preview = build_preview(root)
    return {
        "files": [{"path": item.path, "change": item.change} for item in preview.files],
        "unexpected": preview.unexpected,
        "guard_violations": preview.guard_violations,
        "commit_message": preview.commit_message,
        "blocked": preview.blocked,
    }


def _indexnow_urls_from_files(paths: list[str]) -> set[str]:
    """Public URLs to notify, derived from the same committed-file list the diff
    preview already computes. No separate change tracking. Empty when a deploy
    touched nothing a search engine would refetch, such as a DB-only sync."""
    urls: set[str] = set()
    for path in paths:
        if path.startswith("site/src/content/producers/_published/") and path.endswith(".mdx"):
            urls.add(f"{SITE_URL}/producer/{Path(path).stem}/")
        elif path.startswith("site/src/content/blog/_published/") and path.endswith(".mdx"):
            urls.add(f"{SITE_URL}/blog/{Path(path).stem}/")
    if urls:
        urls.add(f"{SITE_URL}/")
    return urls


def _ping_indexnow(urls: set[str]) -> Iterator[LogLine]:
    """Tells IndexNow-participating engines exactly which pages changed rather
    than waiting for the next scheduled crawl. Called only once Netlify has
    confirmed the build is live, so no engine fetches a page before the content
    is there. Non-fatal in every branch (UX.md §1.5 row 26)."""
    if not urls:
        return
    if not INDEXNOW_KEY:
        yield LogLine(_now(), "info", "indexnow: no key set, skipping")
        return
    yield LogLine(_now(), "info", f"indexnow: notifying {len(urls)} url(s)")
    try:
        response = httpx.post(
            INDEXNOW_ENDPOINT,
            json={
                "host": SITE_URL.split("//", 1)[-1],
                "key": INDEXNOW_KEY,
                "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
                "urlList": sorted(urls),
            },
            timeout=15,
        )
        if response.status_code in (200, 202):
            yield LogLine(_now(), "info", "indexnow: accepted")
        else:
            yield LogLine(
                _now(), "warn", f"indexnow: {response.status_code} {response.text[:200]}"
            )
    except httpx.HTTPError as exc:
        yield LogLine(_now(), "warn", f"indexnow: request failed, {exc}")


def _site_build_gate(site_dir: Path = SITE_DIR) -> Iterator[LogLine]:
    """`npm run build` before the push, streaming into the log pane.

    A failure raises `DeployRefused` (UX.md §1.5 row 23): the commit, if one has
    already been made, stands, and the push does not happen. Broken content that
    reaches Netlify fails there instead, where the admin cannot see it.
    """
    if shutil.which("npm") is None:
        raise DeployRefused(
            "npm is not on the path, so the pre-push build could not run. "
            "Install Node, or deploy from a checkout that has it."
        )
    yield LogLine(_now(), "info", "verifying the site build (npm run build)")
    # The key file route reads INDEXNOW_KEY from the build environment, and the
    # hand-rolled `.env` parser deliberately does not populate `os.environ`, so
    # it is passed explicitly. This gate is a local rehearsal: Netlify builds
    # from the pushed repository and needs the key set in its own environment.
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=site_dir,
        capture_output=True,
        text=True,
        timeout=SITE_BUILD_TIMEOUT_SECONDS,
        env={**os.environ, "INDEXNOW_KEY": INDEXNOW_KEY},
    )
    if result.returncode == 0:
        yield LogLine(_now(), "info", "site build ok")
        return
    output = f"{result.stdout}\n{result.stderr}".strip().splitlines()
    for line in output[-BUILD_LOG_TAIL_LINES:]:
        yield LogLine(_now(), "error", line)
    raise DeployRefused("the site build failed. Fix the content above, then deploy.")


def _netlify_log_url(deploy: dict | None) -> str:
    if deploy and deploy.get("admin_url") and deploy.get("id"):
        return f"{deploy['admin_url']}/deploys/{deploy['id']}"
    if NETLIFY_SITE_ID:
        return f"https://app.netlify.com/sites/{NETLIFY_SITE_ID}/deploys"
    return "https://app.netlify.com"


def _poll_netlify(commit_sha: str, indexnow_urls: set[str]) -> Iterator[LogLine]:
    """Watch the build the push triggered until it is ready or fails.

    This closes the gap where "push ok" reads as a successful deploy while the
    site build failed. Every unresolved branch reports `pushed, build status
    unknown` with the build id and a link to the Netlify log, which is the truth
    (UX.md §1.5 row 25).
    """
    if not (NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID):
        yield LogLine(
            _now(),
            "info",
            "pushed. Netlify builds automatically. Set NETLIFY_AUTH_TOKEN and "
            "NETLIFY_SITE_ID in .env to see build status here, which is also "
            "what fires the IndexNow ping once the build is live.",
        )
        return

    url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
    headers = {"Authorization": f"Bearer {NETLIFY_AUTH_TOKEN}"}
    deadline = time.monotonic() + NETLIFY_POLL_TIMEOUT_SECONDS
    last_state = None
    deploy: dict | None = None

    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, headers=headers, params={"per_page": 10}, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            yield LogLine(
                _now(),
                "warn",
                f"pushed, build status unknown: the Netlify poll failed, {exc}. "
                f"Build log: {_netlify_log_url(deploy)}",
            )
            return
        deploy = next(
            (
                item
                for item in response.json()
                if (item.get("commit_ref") or "").startswith(commit_sha)
            ),
            None,
        )
        state = deploy.get("state") if deploy else None
        if state is not None and state != last_state:
            yield LogLine(_now(), "info", f"netlify: {state} (build {deploy.get('id', '')})")
            last_state = state
        if state == "ready":
            live = deploy.get("ssl_url") or deploy.get("url") or SITE_URL
            yield LogLine(_now(), "info", f"netlify: live at {live}")
            yield from _ping_indexnow(indexnow_urls)
            return
        if state == "error":
            message = deploy.get("error_message") or "build failed"
            if "no content change" in message:
                yield LogLine(_now(), "info", "netlify: skipped the build, no site content changed")
            else:
                yield LogLine(
                    _now(),
                    "error",
                    f"netlify: {message}. Build log: {_netlify_log_url(deploy)}",
                )
            return
        time.sleep(NETLIFY_POLL_INTERVAL_SECONDS)

    yield LogLine(
        _now(),
        "warn",
        f"pushed, build status unknown: the build was still running after "
        f"{NETLIFY_POLL_TIMEOUT_SECONDS // 60} min. "
        f"Build log: {_netlify_log_url(deploy)}",
    )


def run_deploy(
    commit_message: str,
    root: Path = ROOT,
    site_dir: Path = SITE_DIR,
) -> Iterator[LogLine]:
    """The deploy, as a stream of log lines. Every step reports, in order.

    The caller holds `DEPLOY_LOCK` for the duration. `root` and `site_dir` are
    parameters so check 15 can run the whole sequence against a fixture
    repository, offline, with no remote of consequence.
    """
    # Sync first. A checkout that is behind origin has its push rejected at the
    # end, after the build gate has already spent ten minutes.
    yield LogLine(_now(), "info", "git pull --ff-only")
    pull = _run_git("pull", "--ff-only", root=root)
    if pull.returncode != 0:
        yield LogLine(
            _now(), "error", f"git pull failed: {(pull.stderr or pull.stdout).strip()}"
        )
        return

    preview = build_preview(root)

    if preview.guard_violations:
        yield LogLine(
            _now(),
            "error",
            "refused: tracked files under a gitignored path: "
            + ", ".join(preview.guard_violations),
        )
        return
    if preview.unexpected:
        yield LogLine(
            _now(),
            "error",
            "refused: changed files outside the publish set: "
            + ", ".join(preview.unexpected),
        )
        return
    if not preview.files:
        yield LogLine(_now(), "warn", "nothing to deploy, no changes in the publish set")
        return

    try:
        yield from _site_build_gate(site_dir)
    except DeployRefused as exc:
        yield LogLine(_now(), "error", f"refused: {exc}")
        return
    except subprocess.TimeoutExpired:
        yield LogLine(
            _now(),
            "error",
            f"refused: the site build timed out after "
            f"{SITE_BUILD_TIMEOUT_SECONDS // 60} min",
        )
        return

    paths = preview.paths
    yield LogLine(_now(), "info", f"add {len(paths)} file(s)")
    add = _run_git("add", "--", *paths, root=root)
    if add.returncode != 0:
        yield LogLine(_now(), "error", f"git add failed: {add.stderr.strip()}")
        return

    message = commit_message.strip() or preview.commit_message
    yield LogLine(_now(), "info", f"commit: {message}")
    commit = _run_git("commit", "-m", message, root=root)
    if commit.returncode != 0:
        yield LogLine(
            _now(), "error", f"git commit failed: {(commit.stderr or commit.stdout).strip()}"
        )
        return
    first_line = commit.stdout.strip().splitlines()[0] if commit.stdout.strip() else "commit ok"
    yield LogLine(_now(), "info", first_line)

    yield LogLine(_now(), "info", "push")
    push = _run_git("push", root=root)
    if push.returncode != 0:
        # UX.md §1.5 row 24: the actual git error, never "something went wrong".
        yield LogLine(
            _now(), "error", f"git push failed: {(push.stderr or push.stdout).strip()}"
        )
        return
    yield LogLine(_now(), "info", "push ok")

    sha = _run_git("rev-parse", "HEAD", root=root).stdout.strip()
    yield from _poll_netlify(sha, _indexnow_urls_from_files(paths))
