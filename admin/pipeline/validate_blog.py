"""validate_blog.py — `/validate` check 22, blog integrity. Gate 11.

The rules SCHEMA.md §9.3 assigns to Python because zod cannot see them: a claim
audit is a file outside the content collection, and a typed figure is a fact
about the repository rather than about the frontmatter.

── What zod already owns, and is therefore not repeated here ────────────────

The cover co-requirements, the `updated` ordering, duplicate source URLs, the
160-character summary bound and `.strict()` all fail `astro build` with a
field-level error. Re-asserting them here would be a second implementation of
the same rule, and the second one is the one that drifts.

This check owns the three that zod structurally cannot:

**Rule 4 — the audit must resolve.** `data/factchecks/<factcheck>.json` must
exist, parse, name this post, and carry no claim in the `unsupported` state.
Publishing is blocked on an unresolved claim in the admin (UX.md §6); this is
the standing audit that says so about what is *already* published, because a
post can reach `_published` by a route that is not the screen.

**Rule 5 — no hardcoded figures.** A numeral in a body stating a count this
repository holds is a defect (UX.md §6), and it is one nothing else catches: a
typed `97 producers` renders perfectly, reads correctly, and is wrong after the
next harvest with nobody told.

**Rule 6 — a removed claim stayed removed.** The fact-check refuses to return a
`removed` claim whose sentence is still in the body it hands back, but that rule
only ever ran at the moment the model answered. UX.md §6 lets a published post be
edited in place and `save_post` writes those edits straight into `_published`, so
nothing re-checked the body that actually ships. A post could carry, verbatim,
the claim its own audit records as deleted-for-being-false, and every check
passed. Added 2026-08-13 after exactly that was reproduced against the shipped
corpus.

**The removed claims are still recorded.** A `removed` verdict whose text is
gone from the audit is a deletion that left no trace, which UX.md §6 says is
indistinguishable from a claim that was never made.

── Why this fails rather than warns ─────────────────────────────────────────

Check 6 warns because register drift is a judgement a human makes in context.
Everything here is factual: a missing audit, an unresolved claim and a stale
typed count are each either true or not, and none of them improves by being
read and shrugged at. Same footing as checks 8, 9, 10 and 14.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import BLOG_PUBLISHED_DIR, FACTCHECKS_DIR, ROOT  # noqa: E402
from admin.pipeline import blog  # noqa: E402
from admin.pipeline.article_factcheck import typed_figures  # noqa: E402
from admin.schema import FrontmatterError, read_mdx  # noqa: E402

_FIGURE_TAG = re.compile(r'<Figure\s+of="([a-z]+)"(?:\s+member="([^"]*)")?\s*/>')


def _figure_queries(body: str) -> list[tuple[str, str | None]]:
    return [(m.group(1), m.group(2)) for m in _FIGURE_TAG.finditer(body)]


def _clip(value: Any, limit: int) -> str:
    """Quote a fragment in an error, ellipsised only when it was actually cut."""
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit]}…"


def run(
    directory: Path = BLOG_PUBLISHED_DIR,
    factchecks: Path = FACTCHECKS_DIR,
) -> tuple[list[str], list[str], dict[str, int]]:
    """`(errors, notes, stats)` across every published post."""
    errors: list[str] = []
    notes: list[str] = []
    stats = {"posts": 0, "claims": 0, "removed": 0, "figures": 0}

    if not directory.is_dir():
        return errors, notes, stats

    for path in sorted(directory.glob("*.mdx")):
        slug = path.stem
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path

        try:
            data, body = read_mdx(path)
        except FrontmatterError as exc:
            errors.append(f"{rel}: unreadable ({exc})")
            continue

        stats["posts"] += 1

        # ── Rule 4 — the audit must resolve ───────────────────────────────
        name = str(data.get("factcheck") or "").strip()
        if not name:
            errors.append(f"{rel}: no factcheck field (SCHEMA.md §9.2)")
        else:
            audit_path = factchecks / f"{name}.json"
            if not audit_path.is_file():
                errors.append(
                    f"{rel}: names factcheck {name!r} and "
                    f"data/factchecks/{name}.json does not exist (§9.3 rule 4)"
                )
            else:
                try:
                    audit = json.loads(audit_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"data/factchecks/{name}.json: unparseable ({exc})")
                    audit = None

                if isinstance(audit, dict):
                    errors.extend(_check_audit(audit, name, slug, stats, body))
                    if audit.get("self_review"):
                        # A note rather than an error. The post is published and
                        # the audit says plainly that the drafting model checked
                        # itself, which is the thing worth surfacing; failing
                        # would demand a re-check nobody can do retroactively.
                        notes.append(
                            f"{rel}: its claim audit records self_review — the "
                            f"fact-check ran on the drafting model. The audit is "
                            f"worth less than it looks (CLAUDE.md Gate 11)."
                        )
                elif audit is not None:
                    errors.append(f"data/factchecks/{name}.json: not a JSON object")

        # ── Rule 5 — no hardcoded figures ─────────────────────────────────
        for hit in typed_figures(body):
            errors.append(
                f"{rel}: typed figure {hit!r}. A count this repository holds is "
                f"a <Figure>, never typed prose (SCHEMA.md §9.3 rule 5, UX.md §6)."
            )

        stats["figures"] += len(_figure_queries(body))

    return errors, notes, stats


def _check_audit(
    audit: dict[str, Any],
    name: str,
    slug: str,
    stats: dict[str, int],
    body: str,
) -> list[str]:
    errors: list[str] = []

    if str(audit.get("post") or "") != name:
        errors.append(
            f"data/factchecks/{name}.json: its `post` is "
            f"{audit.get('post')!r}, which does not match the file it is named for"
        )

    claims = audit.get("claims")
    if not isinstance(claims, list):
        return errors + [f"data/factchecks/{name}.json: `claims` is not an array"]

    stats["claims"] += len(claims)

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"data/factchecks/{name}.json: claims[{index}] is not an object")
            continue

        verdict = claim.get("verdict")
        if verdict not in blog.CLAIM_VERDICTS:
            errors.append(
                f"data/factchecks/{name}.json: claims[{index}].verdict is "
                f"{verdict!r}; SCHEMA.md §9.4 closes the set at "
                f"{', '.join(blog.CLAIM_VERDICTS)}"
            )
            continue

        if verdict == blog.BLOCKING_VERDICT:
            errors.append(
                f"{slug}: claim {claim.get('id')} is still unresolved "
                f"({str(claim.get('text', ''))[:70]}…). A post does not publish "
                f"with an unresolved claim (UX.md §6)."
            )

        if verdict == "removed":
            stats["removed"] += 1
            # The record IS the deletion. A removed claim with no text is a
            # deletion that left no trace, which is exactly what UX.md §6 says
            # is indistinguishable from a claim that was never made.
            if not str(claim.get("text") or "").strip():
                errors.append(
                    f"data/factchecks/{name}.json: claims[{index}] is removed and "
                    f"carries no `text`. The verbatim sentence is the record; "
                    f"without it the deletion left no trace (UX.md §6)."
                )

        if verdict == "supported" and not str(claim.get("source") or "").strip():
            errors.append(
                f"data/factchecks/{name}.json: claims[{index}] is supported and "
                f"names no source"
            )

        if not str(claim.get("reason") or "").strip():
            errors.append(
                f"data/factchecks/{name}.json: claims[{index}] carries no reason"
            )

    # ── Rule 6 — a removed claim stayed removed ───────────────────────────
    #
    # The comparison is `blog.restored_claims`, which is the same function the
    # publish gate uses and the same exact-substring test the fact-check applies
    # to its own output. One implementation, three call sites: a second one here
    # would be the one that drifts.
    for claim in blog.restored_claims(body, audit):
        errors.append(
            f"{slug}: claim {claim.get('id')} is verdicted removed and its text is "
            f"still in the published body: “{_clip(claim.get('text'), 70)}”. It was "
            f"removed because: “{_clip(claim.get('reason'), 120)}”. "
            f"A deletion the post did not make is not a deletion "
            f"(SCHEMA.md §9.3 rule 6, UX.md §6)."
        )

    return errors


# =============================================================================
# Self-test — validate.md's pattern
# =============================================================================


def _write(directory: Path, slug: str, frontmatter: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{slug}.mdx").write_text(
        f"---\n{frontmatter}---\n\n{body}\n", encoding="utf-8"
    )


_CLEAN_FRONTMATTER = """title: A clean post
summary: A summary.
dateline: Australia
published: 2026-08-13
sources:
  - title: ABN Lookup
    url: https://abr.business.gov.au/
factcheck: clean
"""

_CLEAN_AUDIT = {
    "post": "clean",
    "checked": "2026-08-13",
    "model": "check-model",
    "drafted_by": "draft-model",
    "claims": [
        {
            "id": "c1",
            "text": "The register carries no shareholder data.",
            "verdict": "supported",
            "reason": "ABN Lookup publishes entity name and status only.",
            "source": "https://abr.business.gov.au/",
        },
        {
            "id": "c2",
            "text": "Most producers have been in the same family for generations.",
            "verdict": "removed",
            "reason": "Nothing in the corpus supports it.",
            "source": None,
        },
    ],
}


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    import copy
    import tempfile

    errors: list[str] = []

    def fixture(
        tmp: Path,
        *,
        frontmatter: str = _CLEAN_FRONTMATTER,
        body: str = 'The guide documents <Figure of="published" /> producers.',
        audit: dict[str, Any] | None = None,
        audit_name: str = "clean",
    ) -> tuple[Path, Path]:
        posts, checks = tmp / "posts", tmp / "checks"
        _write(posts, "clean", frontmatter, body)
        if audit is not None:
            checks.mkdir(parents=True, exist_ok=True)
            (checks / f"{audit_name}.json").write_text(
                json.dumps(audit), encoding="utf-8"
            )
        return posts, checks

    # The clean fixture must pass, or every failure below proves nothing.
    with tempfile.TemporaryDirectory() as tmp:
        posts, checks = fixture(Path(tmp), audit=copy.deepcopy(_CLEAN_AUDIT))
        found, _notes, stats = run(posts, checks)
        if found:
            errors.append(f"selftest: the CLEAN fixture failed: {found}")
        if stats["figures"] != 1:
            errors.append("selftest: the clean fixture's <Figure> was not counted")
        if stats["removed"] != 1:
            errors.append("selftest: the clean fixture's removed claim was not counted")

    #: `(mutate, the phrase the error must name, why)`. Requiring the error to
    #: NAME the thing it broke is what keeps a case from passing for an
    #: unrelated reason — an error is not evidence if it fires by accident.
    cases: list[tuple[Any, str, str]] = [
        (
            lambda f, b, a: (f, "The guide documents 97 producers.", a),
            "typed figure",
            "a typed producer count",
        ),
        # The sentence shape a person actually writes. The first version of the
        # scan required the noun adjacent to the numeral and read straight past
        # this, while the fixture above passed — a fixture testing what it was
        # written against rather than the defect (Gate 9's carried-forward
        # note 1, in a different disguise).
        (
            lambda f, b, a: (
                f, "The guide documents 97 independent Australian winemakers.", a),
            "typed figure",
            "a typed count separated from its noun by adjectives",
        ),
        (
            lambda f, b, a: (f, "There are 12 registered regions here.", a),
            "typed figure",
            "a typed region count",
        ),
        (
            lambda f, b, a: (f, b, None),
            "does not exist",
            "a missing claim audit",
        ),
        (
            lambda f, b, a: (f, b, {**a, "claims": [
                {**a["claims"][0], "verdict": "unsupported", "source": None}]}),
            "still unresolved",
            "an unresolved claim",
        ),
        (
            lambda f, b, a: (f, b, {**a, "claims": [
                {**a["claims"][1], "text": ""}]}),
            "left no trace",
            "a removed claim with no text",
        ),
        # Rule 6. The defect this check was extended for: the sentence the audit
        # records as removed, back in the published body. It reproduced against
        # the real corpus and passed clean before this case existed.
        (
            lambda f, b, a: (f, f"{b}\n\n{a['claims'][1]['text']}", a),
            "still in the published body",
            "a removed claim whose text is back in the body",
        ),
        (
            lambda f, b, a: (f, b, {**a, "claims": [
                {**a["claims"][0], "source": None}]}),
            "names no source",
            "a supported claim with no source",
        ),
        (
            lambda f, b, a: (f, b, {**a, "claims": [
                {**a["claims"][0], "reason": "  "}]}),
            "carries no reason",
            "a claim with no reason",
        ),
        (
            lambda f, b, a: (f, b, {**a, "claims": [
                {**a["claims"][0], "verdict": "probably"}]}),
            "closes the set",
            "an unknown verdict",
        ),
        (
            lambda f, b, a: (f, b, {**a, "post": "something-else"}),
            "does not match",
            "an audit naming a different post",
        ),
        (
            lambda f, b, a: (f.replace("factcheck: clean\n", ""), b, a),
            "no factcheck field",
            "a post naming no audit",
        ),
    ]

    for mutate, phrase, why in cases:
        with tempfile.TemporaryDirectory() as tmp:
            frontmatter, body, audit = mutate(
                _CLEAN_FRONTMATTER,
                'The guide documents <Figure of="published" /> producers.',
                copy.deepcopy(_CLEAN_AUDIT),
            )
            posts, checks = fixture(
                Path(tmp), frontmatter=frontmatter, body=body, audit=audit
            )
            found, _notes, _stats = run(posts, checks)
            if not found:
                errors.append(f"selftest: {why} was NOT caught")
            elif not any(phrase in error for error in found):
                errors.append(
                    f"selftest: {why} was caught, but no error named {phrase!r}. "
                    f"Got: {found[:2]}"
                )

    # A self-review audit is a NOTE, not an error. Failing would demand a
    # re-check nobody can do retroactively on a published post.
    with tempfile.TemporaryDirectory() as tmp:
        audit = {**copy.deepcopy(_CLEAN_AUDIT), "self_review": True}
        posts, checks = fixture(Path(tmp), audit=audit)
        found, notes, _stats = run(posts, checks)
        if found:
            errors.append(f"selftest: a self-review audit was treated as an error: {found}")
        if not any("self_review" in note for note in notes):
            errors.append("selftest: a self-review audit was not reported as a note")

    # The typed-figure scan must not fire on ordinary numerals.
    with tempfile.TemporaryDirectory() as tmp:
        posts, checks = fixture(
            Path(tmp),
            body="The vineyard was planted in 1989 and tastings cost $15.",
            audit=copy.deepcopy(_CLEAN_AUDIT),
        )
        found, _notes, _stats = run(posts, checks)
        if found:
            errors.append(f"selftest: a false positive on ordinary numerals: {found}")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print(f"VALIDATE 22 FAIL — {len(errors)} self-test issue(s)")
        for message in errors:
            print(f"  {message}")
        return 1

    found, notes, stats = run()

    for note in notes:
        print(f"  note: {note}")

    if found:
        print(f"VALIDATE 22 FAIL — {len(found)} issue(s)")
        for message in found:
            print(f"  {message}")
        return 1

    print(
        f"VALIDATE 22 PASS — {stats['posts']} published post(s), "
        f"{stats['claims']} claim(s) audited ({stats['removed']} removed and "
        f"recorded), {stats['figures']} <Figure> tag(s), no typed counts"
        + (f"; {len(notes)} note(s)" if notes else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
