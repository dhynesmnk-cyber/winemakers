"""blog.py — the post store and the publish gate. UX.md §6, SCHEMA.md §9. Gate 11.

Posts are hand-authored and editorially drafted rather than harvested, so this
module is the blog's `staging.py` and deliberately not a branch of it. The two
workflows share almost nothing: there is no queue, no ownership determination, no
deny-list, no confidence tier, no derived database and no undo window.

── The second surface of a two-surface contract ─────────────────────────────

`POST_FIELDS` below is consumer 2 of 2 for SCHEMA.md §9 (the zod schema in
`site/src/content/config.ts` is consumer 1). CLAUDE.md rule 7's four-surface rule
governs the PRODUCER contract; §9.1 records why a post has two and what the
missing two would have been. `/validate` check 13 diffs this pair, so a field
added here and not there fails the same way a producer field does.

── Publish is a gate, not a button ──────────────────────────────────────────

UX.md §6: publish is blocked while any fact-check claim is unresolved, and
blocked while title, summary or dateline is missing, **with the specific missing
element named**. `publish_blocks()` returns those reasons as strings and the
screen renders them; the block is never a disabled control with no stated cause,
which UX.md §5 calls a UX bug against the specification.

── Deleting ─────────────────────────────────────────────────────────────────

A draft is deleted outright, with no reject-and-keep, because there is no
harvested output to preserve a record of (UX.md §6). Deleting an already
published post is not offered at all. That asymmetry is deliberate: publishing is
a considered action and unpublishing by a stray keystroke is not one.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    ARTICLE_STAGING_DIR,
    BLOG_PUBLISHED_DIR,
    BLOG_STAGING_DIR,
    FACTCHECKS_DIR,
    SITE_DIR,
)
from admin.schema import (  # noqa: E402
    FrontmatterError,
    coerce_dates,
    parse_mdx_text,
    read_mdx,
)

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    """Default logger. The store is usable from a CLI with no log pane."""


#: Published post images. Committed, and on the deploy allow-list (TRD.md §6.5).
BLOG_IMAGES_DIR = SITE_DIR / "public" / "blog-images"

#: Staged post images, before publish. Gitignored volume state.
BLOG_STAGING_IMAGES_DIR = BLOG_STAGING_DIR / "_images"


# =============================================================================
# 1. The field contract — SCHEMA.md §9.2. Consumer 2 of 2.
# =============================================================================

#: Every field a post carries, in the order `write_post` writes them.
#:
#: NAME-MATCHED with the zod schema in `site/src/content/config.ts`. Adding a
#: field to one without the other fails `/validate` check 13.
POST_FIELDS: tuple[str, ...] = (
    "title",
    "summary",
    "dateline",
    "published",
    "updated",
    "sources",
    "factcheck",
    "cover",
    "cover_source",
    "cover_caption",
)

#: The three UX.md §6 names by which publish is blocked when missing, plus the
#: two SCHEMA.md §9.2 requires that the editor does not surface as a text input.
REQUIRED_FIELDS: tuple[str, ...] = ("title", "summary", "dateline", "published", "sources", "factcheck")

#: SCHEMA.md §9.4. The three verdicts, and which of them blocks a publish.
CLAIM_VERDICTS: tuple[str, ...] = ("supported", "unsupported", "removed")
BLOCKING_VERDICT = "unsupported"

#: SCHEMA.md §9.2, matching the producer `summary` bound and for the same reason.
SUMMARY_MAX = 160


# =============================================================================
# 2. Slugs and paths
# =============================================================================

_SLUG_OK = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(title: str) -> str:
    """A kebab-case slug from a title. The filename, and therefore the route."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def is_slug(slug: str) -> bool:
    return bool(_SLUG_OK.match(slug))


def _guard(slug: str) -> str:
    """Refuse anything that is not a bare kebab-case slug.

    Every path below is built by joining this to a directory, and a slug
    arriving from an HTTP route is untrusted input. `..` or a leading `/` would
    otherwise write outside the staging tree.
    """
    if not is_slug(slug):
        raise ValueError(f"not a valid post slug: {slug!r}")
    return slug


def staged_path(slug: str) -> Path:
    return BLOG_STAGING_DIR / f"{_guard(slug)}.mdx"


def published_path(slug: str) -> Path:
    return BLOG_PUBLISHED_DIR / f"{_guard(slug)}.mdx"


def factcheck_path(slug: str) -> Path:
    return FACTCHECKS_DIR / f"{_guard(slug)}.json"


def brief_path(slug: str) -> Path:
    """The article brief, retained in `_article_staging` beside its working notes."""
    return ARTICLE_STAGING_DIR / f"{_guard(slug)}.json"


def path_for(slug: str) -> Path | None:
    """Wherever this post lives, published first. `None` when it does not exist."""
    for path in (published_path(slug), staged_path(slug)):
        if path.is_file():
            return path
    return None


def is_published(slug: str) -> bool:
    return published_path(slug).is_file()


# =============================================================================
# 3. Reading and writing
# =============================================================================


def write_post(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write a post in `POST_FIELDS` order, with the producer dumper.

    Ordering by the contract rather than by the incoming dict is what keeps a
    hand-edited file and a pipeline-written one byte-comparable, and keeps an
    autosave from reshuffling the file under the author on every keystroke. Same
    reasoning as `schema.write_mdx`, whose dumper this borrows rather than
    reimplements — one YAML dialect in the repository, not two.
    """
    import yaml

    from admin.schema import _BlockSequenceDumper

    ordered: dict[str, Any] = {}
    for field in POST_FIELDS:
        if field in frontmatter and frontmatter[field] is not None:
            ordered[field] = frontmatter[field]
    # Unknown keys are preserved and written last. A `.strict()` violation is the
    # author's to see and delete, never this function's to silently swallow.
    for field in frontmatter:
        if field not in ordered and frontmatter[field] is not None:
            ordered[field] = frontmatter[field]

    dumped = yaml.dump(
        ordered,
        Dumper=_BlockSequenceDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10**9,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{dumped}---\n\n{body.strip(chr(10))}\n", encoding="utf-8")


def load_post(slug: str) -> tuple[dict[str, Any], str]:
    """`(frontmatter, body)` for a post in either directory."""
    path = path_for(slug)
    if path is None:
        raise FileNotFoundError(f"no post at {slug}")
    return read_mdx(path)


def save_post(slug: str, frontmatter: dict[str, Any], body: str) -> Path:
    """Autosave. Writes back wherever the post already lives.

    UX.md §6: "Editing an already-published post updates it in place. No
    re-publish step." So a published post is saved straight to `_published`,
    which is the ONE sanctioned exception to CLAUDE.md rule 5's "only the approve
    action writes there" — that rule is about the producer collection, and this
    is the author editing their own live post through the screen built for it.
    """
    path = published_path(slug) if is_published(slug) else staged_path(slug)
    write_post(path, coerce_dates(frontmatter), body)
    return path


def create_draft(title: str, log: Logger = _null_log) -> str:
    """Start a draft. Returns the slug.

    The slug is minted from the title once, here, and never recomputed on a
    later rename: the slug is the route, and a published post whose URL moved
    because somebody fixed a typo in the title is a broken link on every page
    that ever cited it.
    """
    slug = slugify(title)
    if path_for(slug) is not None:
        stamp = datetime.now().strftime("%H%M%S")
        slug = f"{slug}-{stamp}"

    write_post(
        staged_path(slug),
        {
            "title": title,
            "summary": "",
            "dateline": "",
            "published": date.today(),
            "sources": [],
            "factcheck": slug,
        },
        "",
    )
    log("info", f"blog: started draft {slug}")
    return slug


def delete_draft(slug: str, log: Logger = _null_log) -> None:
    """Remove an unpublished draft outright (UX.md §6).

    No reject-and-keep, because there is no harvested output to preserve a record
    of. A published post is never deleted from here.
    """
    if is_published(slug):
        raise ValueError(
            f"{slug} is published. Deleting a published post is not offered; "
            f"publishing is a considered action (UX.md §6)."
        )
    path = staged_path(slug)
    if path.is_file():
        path.unlink()
    # The brief and the claim audit are working state for an unpublished draft
    # and go with it. A published post's audit is committed record and stays.
    for extra in (brief_path(slug), factcheck_path(slug)):
        if extra.is_file():
            extra.unlink()
    log("info", f"blog: deleted draft {slug}")


# =============================================================================
# 4. The claim audit — SCHEMA.md §9.4
# =============================================================================


def load_factcheck(slug: str) -> dict[str, Any] | None:
    """The committed claim audit, or `None` when the post has not been checked."""
    path = factcheck_path(slug)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_factcheck(slug: str, audit: dict[str, Any]) -> Path:
    """Write the audit with sorted keys and a trailing newline.

    Byte-stable between writes for the same reason every other committed
    artefact in this project is: it is committed, and a file that reorders
    itself makes every deploy diff unreadable.
    """
    path = factcheck_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def unresolved_claims(slug: str) -> list[dict[str, Any]]:
    """Claims the fact-check could not stand up and a person has not resolved."""
    audit = load_factcheck(slug)
    if audit is None:
        return []
    return [
        claim
        for claim in audit.get("claims", [])
        if claim.get("verdict") == BLOCKING_VERDICT
    ]


def restored_claims(body: str, audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Claims verdicted `removed` whose sentence is back in the body.

    The fact-check refuses to RETURN a `removed` claim whose text is still in the
    body it hands back (`article_factcheck._validate_result`). This is that same
    comparison, standing watch over the body the post actually carries later.

    It is needed because the rule had no second half. UX.md §6 lets a published
    post be edited in place and `save_post` writes those edits straight into
    `_published`, so between the fact-check answering and the post shipping there
    was nothing asserting that a sentence deleted for being false had stayed
    deleted. A post could carry, verbatim, the claim its own committed audit
    records as removed, with the whole suite green.

    Exact substring, deliberately the same test as the draft-time one. Two
    comparisons that agree today and drift tomorrow would be worse than one.
    """
    if not audit:
        return []
    return [
        claim
        for claim in audit.get("claims", [])
        if claim.get("verdict") == "removed"
        and str(claim.get("text") or "").strip()
        and str(claim["text"]).strip() in body
    ]


def resolve_claim(
    slug: str, claim_id: str, verdict: str, reason: str, source: str | None = None
) -> dict[str, Any]:
    """Record a person's resolution of an `unsupported` claim.

    The reviewer moves a claim to `supported` by naming the source they found, or
    to `removed` having deleted the sentence themselves. **They cannot move it
    without saying why**: `reason` is required, because the audit is committed
    record and "resolved" with no reason is indistinguishable from a claim
    nobody looked at.
    """
    if verdict not in CLAIM_VERDICTS:
        raise ValueError(f"verdict must be one of {CLAIM_VERDICTS}, got {verdict!r}")
    if verdict == BLOCKING_VERDICT:
        raise ValueError(
            f"resolving a claim to {BLOCKING_VERDICT!r} is not a resolution. "
            f"Find the source, edit the claim, or remove it."
        )
    if not reason.strip():
        raise ValueError("a resolution must state a reason (SCHEMA.md §9.4)")
    if verdict == "supported" and not (source or "").strip():
        raise ValueError("resolving a claim to supported requires the source that stands it up")

    audit = load_factcheck(slug)
    if audit is None:
        raise FileNotFoundError(f"no claim audit for {slug}")

    for claim in audit.get("claims", []):
        if claim.get("id") == claim_id:
            claim["verdict"] = verdict
            claim["reason"] = reason.strip()
            claim["source"] = (source or "").strip() or None
            claim["resolved_by"] = "reviewer"
            claim["resolved_on"] = date.today().isoformat()
            save_factcheck(slug, audit)
            return claim

    raise KeyError(f"no claim {claim_id!r} in the audit for {slug}")


# =============================================================================
# 5. The publish gate — UX.md §6
# =============================================================================


def publish_blocks(slug: str) -> list[str]:
    """Every reason this post cannot publish, in plain words. Empty means it can.

    UX.md §6 requires the SPECIFIC missing element to be named, so every string
    here is actionable on its own. A caller renders the list; nothing disables a
    control without printing its cause.
    """
    blocks: list[str] = []

    try:
        data, body = load_post(slug)
    except (FileNotFoundError, FrontmatterError) as exc:
        return [f"The post could not be read: {exc}"]

    for field in ("title", "summary", "dateline"):
        if not str(data.get(field) or "").strip():
            blocks.append(f"{field} is empty. A post cannot publish without it.")

    summary = str(data.get("summary") or "")
    if len(summary) > SUMMARY_MAX:
        blocks.append(
            f"summary is {len(summary)} characters; the limit is {SUMMARY_MAX} "
            f"(SCHEMA.md §9.2). It is the index line and the meta description."
        )

    if not data.get("published"):
        blocks.append("published has no date.")

    sources = data.get("sources") or []
    if not sources:
        blocks.append(
            "sources is empty. Every post lists what it was written from "
            "(SCHEMA.md §9.2); a post with no sources is an opinion."
        )
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict) or not source.get("title") or not source.get("url"):
                blocks.append(f"sources[{index}] needs both a title and a url.")

    if not str(data.get("factcheck") or "").strip():
        blocks.append("factcheck does not name a claim audit.")
    elif load_factcheck(str(data["factcheck"])) is None:
        blocks.append(
            f"no claim audit at data/factchecks/{data['factcheck']}.json. "
            f"Run the fact-check before publishing."
        )

    audit_name = str(data.get("factcheck") or slug)

    unresolved = unresolved_claims(audit_name)
    for claim in unresolved:
        text = str(claim.get("text", ""))[:90]
        blocks.append(
            f"claim {claim.get('id')} is unresolved: “{text}…” "
            f"Find the source, edit the claim, or remove it."
        )

    # A claim the fact-check deleted, back in the body. Blocked here rather than
    # refused at save time on purpose: the author has to be able to type the
    # sentence in order to rewrite it with a source. They must not be able to
    # publish it.
    for claim in restored_claims(body, load_factcheck(audit_name)):
        text = str(claim.get("text", ""))[:90]
        reason = str(claim.get("reason") or "no reason recorded")[:120]
        blocks.append(
            f"claim {claim.get('id')} was removed by the fact-check and its text is "
            f"back in the body: “{text}…” It was removed because: {reason} "
            f"Delete it again, or resolve the claim with a source that stands it up."
        )

    if data.get("cover"):
        for field in ("cover_source", "cover_caption"):
            if not str(data.get(field) or "").strip():
                blocks.append(
                    f"{field} is required when a cover image is set "
                    f"(SCHEMA.md §9.3 rule 1). A published photograph carries "
                    f"visible attribution."
                )

    if not body.strip():
        blocks.append("The body is empty.")

    return blocks


def publish(slug: str, log: Logger = _null_log) -> dict[str, Any]:
    """Move a staged post into `_published`, carrying its images with it.

    Refuses on any `publish_blocks` reason. The check is here rather than only in
    the route, so a CLI call or a later caller cannot route around the gate.
    """
    if is_published(slug):
        raise ValueError(f"{slug} is already published; edits save in place (UX.md §6).")

    blocks = publish_blocks(slug)
    if blocks:
        raise ValueError("; ".join(blocks))

    data, body = load_post(slug)

    moved = _publish_images(slug, body)
    body = moved["body"]

    destination = published_path(slug)
    write_post(destination, data, body)
    staged_path(slug).unlink(missing_ok=True)

    log("info", f"blog: published {slug} ({moved['count']} image(s) moved)")
    return {"slug": slug, "path": str(destination), "images": moved["count"]}


def _publish_images(slug: str, body: str) -> dict[str, Any]:
    """Move this post's staged images into `site/public/blog-images/`.

    UX.md §6: images convert "in the same action" as the publish, because a
    post's images are part of the authored draft rather than harvested
    candidates needing a curation decision. This is deliberately unlike the
    producer image pipeline (UX.md §4), where publishing an image is its own
    considered step.

    Body references are rewritten from the staging URL to the published one. A
    published post pointing at `/blog-staging/…` would 404 on the live site while
    rendering perfectly in the admin preview, which is the worst shape of defect
    this project has: correct everywhere a person looks.
    """
    count = 0
    source_dir = BLOG_STAGING_IMAGES_DIR / slug
    if source_dir.is_dir():
        BLOG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        for image in sorted(source_dir.iterdir()):
            if image.is_file():
                shutil.copy2(image, BLOG_IMAGES_DIR / image.name)
                count += 1
        shutil.rmtree(source_dir, ignore_errors=True)

    body = body.replace("/blog-staging-images/", "/blog-images/")
    return {"body": body, "count": count}


# =============================================================================
# 6. The post list — UX.md §6's left pane
# =============================================================================


def post_rows() -> list[dict[str, Any]]:
    """Drafts and published posts together, each with a status chip (UX.md §6).

    One list rather than two, because the author's question is "where is that
    post" and splitting the answer across two panes makes them look in both.
    Drafts first, then published, each newest first: the draft you are working on
    is the one you came here for.
    """
    rows: list[dict[str, Any]] = []

    for directory, status in ((BLOG_STAGING_DIR, "draft"), (BLOG_PUBLISHED_DIR, "published")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.mdx")):
            slug = path.stem
            try:
                data, body = read_mdx(path)
            except FrontmatterError as exc:
                rows.append(
                    {
                        "slug": slug,
                        "title": slug,
                        "status": "unreadable",
                        "chip": "UNREADABLE",
                        "detail": str(exc),
                        "published": None,
                        "words": 0,
                        "blocks": 1,
                        "unresolved": 0,
                    }
                )
                continue

            published = data.get("published")
            unresolved = len(unresolved_claims(str(data.get("factcheck") or slug)))
            blocks = publish_blocks(slug) if status == "draft" else []

            rows.append(
                {
                    "slug": slug,
                    "title": str(data.get("title") or slug),
                    "status": status,
                    "chip": _chip(status, blocks, unresolved),
                    "detail": str(data.get("dateline") or ""),
                    "published": published.isoformat() if hasattr(published, "isoformat") else published,
                    "words": len(body.split()),
                    "blocks": len(blocks),
                    "unresolved": unresolved,
                }
            )

    def sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        # Drafts first, then published; within each, newest first. `published`
        # is inverted by sorting descending on the ISO string, which sorts
        # correctly as text because ISO dates are fixed-width.
        return (
            0 if row["status"] != "published" else 1,
            _invert(str(row["published"] or "")),
            row["title"],
        )

    rows.sort(key=sort_key)
    return rows


def _invert(iso: str) -> str:
    """Sort an ISO date descending inside an otherwise ascending key."""
    return "".join(chr(ord("9") - (ord(c) - ord("0"))) if c.isdigit() else c for c in iso)


def _chip(status: str, blocks: list[str], unresolved: int) -> str:
    """The status chip. Unresolved claims outrank every other draft state.

    UX.md §6 makes an unresolved claim the thing that blocks a publish, so it is
    the thing the list says first. A row reading `DRAFT` while carrying three
    claims nobody could stand up tells the author the wrong thing at a glance.
    """
    if status == "published":
        return "PUBLISHED"
    if unresolved:
        return f"{unresolved} CLAIM{'S' if unresolved != 1 else ''} UNRESOLVED"
    if blocks:
        return "DRAFT"
    return "READY"


# =============================================================================
# 7. Self-test — validate.md's pattern
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    import tempfile

    errors: list[str] = []

    if not is_slug("who-owns-the-hills"):
        errors.append("selftest: a valid slug was rejected")
    for bad in ("../etc", "Who-Owns", "a_b", "/abs", "trailing-", ""):
        if is_slug(bad):
            errors.append(f"selftest: {bad!r} was accepted as a slug")
        try:
            staged_path(bad)
        except ValueError:
            continue
        errors.append(f"selftest: staged_path built a path from {bad!r}")

    if slugify("Who owns the Adelaide Hills?") != "who-owns-the-adelaide-hills":
        errors.append("selftest: slugify produced an unexpected slug")

    # A round trip must preserve the body and order the frontmatter by contract.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x.mdx"
        write_post(
            path,
            {
                "factcheck": "x",
                "title": "A title",
                "sources": [{"title": "S", "url": "https://example.com/"}],
                "summary": "A summary.",
                "dateline": "Australia",
                "published": date(2026, 8, 13),
            },
            "Body text.\n",
        )
        text = path.read_text(encoding="utf-8")
        if text.index("title:") > text.index("summary:"):
            errors.append("selftest: write_post did not order fields by POST_FIELDS")
        data, body = parse_mdx_text(text)
        if body.strip() != "Body text.":
            errors.append("selftest: the body did not survive a round trip")
        if data.get("published") != date(2026, 8, 13):
            errors.append("selftest: the published date did not survive a round trip")

    # `resolve_claim` must refuse the three things that would make the audit a
    # rubber stamp: an unknown verdict, a "resolution" back to unsupported, and
    # a resolution with no reason.
    for verdict, reason, source, why in (
        ("maybe", "r", None, "an unknown verdict"),
        (BLOCKING_VERDICT, "r", None, "a resolution back to unsupported"),
        ("supported", "   ", "https://x/", "an empty reason"),
        ("supported", "r", "", "supported with no source"),
    ):
        try:
            resolve_claim("nonexistent-post", "c1", verdict, reason, source)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            if isinstance(exc, ValueError):
                continue
            errors.append(f"selftest: resolve_claim reached the file for {why}")
        else:
            errors.append(f"selftest: resolve_claim ACCEPTED {why}")

    # `restored_claims` — the standing half of the fact-check's own deletion
    # rule. It must fire on a removed sentence that came back and stay quiet on
    # everything else, because a block nobody can clear is a block reviewers
    # learn to route around.
    deleted = "Most producers have been in the same family for generations."
    audit = {
        "claims": [
            {"id": "c1", "text": deleted, "verdict": "removed", "reason": "Unsupported."},
            {"id": "c2", "text": "Production sits under a thousand cases.",
             "verdict": "supported", "reason": "The producer states it."},
            {"id": "c3", "text": "", "verdict": "removed", "reason": "Empty."},
        ]
    }
    if not restored_claims(f"A paragraph.\n\n{deleted}\n\nAnother.", audit):
        errors.append("selftest: a removed claim restored to the body was NOT caught")
    if restored_claims("A body carrying neither sentence.", audit):
        errors.append("selftest: restored_claims fired on a body carrying no removed text")
    if restored_claims("Production sits under a thousand cases.", audit):
        errors.append("selftest: restored_claims fired on a SUPPORTED claim's text")
    if restored_claims("anything at all", None):
        errors.append("selftest: restored_claims fired with no audit")
    if restored_claims("", audit):
        errors.append("selftest: an empty removed `text` matched an empty body")

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print("BLOG FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    rows = post_rows()
    drafts = sum(1 for row in rows if row["status"] == "draft")
    published = sum(1 for row in rows if row["status"] == "published")
    print(f"BLOG — selftest ok; {drafts} draft(s), {published} published")
    for row in rows:
        print(f"  {row['chip']:<24} {row['slug']}  ({row['words']} words)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
