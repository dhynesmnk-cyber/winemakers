"""forewords.py — the aggregation-page forewords. TRD.md §4.8, UX.md §2.4.

GATE 6.

Every programmatic page carries a foreword: prose about the region, the grape or
the practice, not a stitched-together summary of the producers listed below it.

── Drafted once, then owned by a human ───────────────────────────────────────

UX.md §2.4: forewords are "drafted once by the pipeline into ``forewords.json``,
human-editable, and never regenerated on every build. Copy that churns every
build is copy nobody trusts."

So the default pass writes ONLY missing keys. An existing foreword is left
exactly as it is, whether the model wrote it or a person rewrote it afterwards.
Regenerating one is an explicit ``--force`` naming the key, never a side effect
of running the command.

── Failure is non-fatal, per page ────────────────────────────────────────────

UX.md §1.5 row 19: "Foreword generation fails for a new region or variety.
Logged in the warn colour. Non-fatal. The page renders without a foreword rather
than not rendering." One region failing must not cost the other seventy, and the
site must build with an empty ``forewords.json`` — which is exactly the state it
ships in until this is run.

── The honesty rule reaches here too ─────────────────────────────────────────

A foreword is reader-facing prose written by a model, so it gets the same
treatment as a producer entry: ``PROMPTS/foreword.md`` carries the honesty rule
verbatim, and every draft is linted against the SAME banned-word, hedge,
tasting-descriptor and em-dash lists the Gatekeeper is run with, parsed from
``PROMPTS/gatekeeper.md`` by ``validate_register``. There is no second copy of
those lists here (CLAUDE.md, amended 2026-08-07).

A draft that trips the lint is REJECTED and re-asked once, rather than written
and left for someone to notice. That is stricter than the producer pipeline,
where the lint is a warning a human judges. It can afford to be: there are tens
of forewords, not hundreds, and nobody is reviewing them one by one in a queue.

── What the validator cannot do, and why a human still reads these ───────────

It checks SHAPE and REGISTER. It cannot check truth.

The first real run proved the point. Given a facts block listing South
Australia's nineteen registered regions, the model wrote "That is nineteen
registered regions, more than any other state." The count was right and the
comparison was invented: Victoria has twenty-one, and the facts block describes
one subject and never mentions another. No lint catches that, because every word
of it is in register.

The prompt now bans comparatives outright for exactly this reason. But the
durable protection is that forewords are written ONCE and are human-editable:
they are meant to be read before they ship, and this is what that read is for.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from ..config import (
    FOREWORDS_JSON_PATH,
    MODEL_FOREWORD,
    PRODUCERS_JSON_PATH,
    PRACTICE_KEYS,
)
from . import ts_data
from .agents import AgentError, Ledger, MalformedOutput, call, load_prompt
from .validate_register import lint_text, load_lists

Logger = Callable[[str, str], None]

#: Derived from glossary.ts, exactly as `config.ts` derives its own copy. Not a
#: literal in `admin/config.py`: a second hand-kept map would be a drift surface.
STATE_NAMES = ts_data.state_names()

#: The five buckets, in the order they are written. UX.md §2.4: "Forewords for
#: regions, subregions, states, varieties and practices live in separate keyed
#: buckets in the one file."
KINDS = ("region", "subregion", "state", "variety", "practice")

#: Sentence bounds from the prompt. Enforced rather than hoped for: a nine
#: sentence "foreword" is an essay sitting above a producer list.
MIN_SENTENCES = 2
MAX_SENTENCES = 5


# =============================================================================
# 1. What needs a foreword — the same present-only membership the pages use
# =============================================================================


def _published() -> list[dict[str, Any]]:
    if not PRODUCERS_JSON_PATH.is_file():
        return []
    return json.loads(PRODUCERS_JSON_PATH.read_text(encoding="utf-8"))


def targets(producers: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every taxonomy member with at least one published producer.

    Mirrors ``site/src/data/taxonomy.ts``. A member with zero producers
    generates no page, so it needs no foreword, and drafting one would spend a
    model call on a page nobody can reach.
    """
    rows = _published() if producers is None else producers

    counts: dict[tuple[str, str], int] = Counter()
    for row in rows:
        for region in row.get("regions") or []:
            counts[("region", region)] += 1
        for sub in row.get("subregions") or []:
            counts[("subregion", sub)] += 1
        if row.get("state"):
            counts[("state", row["state"])] += 1
        for variety in row.get("varieties") or []:
            counts[("variety", variety)] += 1
        for key in PRACTICE_KEYS:
            if (row.get("practices") or {}).get(key) is True:
                counts[("practice", key)] += 1

    regions = {r["slug"]: r for r in ts_data.regions()}
    subregions = {s["slug"]: s for s in ts_data.subregions()}
    glossary = {(e["vocabulary"], e["value"]): e for e in ts_data.glossary()}

    out: list[dict[str, Any]] = []
    for kind in KINDS:
        for (member_kind, key), count in sorted(counts.items()):
            if member_kind != kind:
                continue
            if kind == "region":
                name = regions.get(key, {}).get("name", key)
            elif kind == "subregion":
                name = subregions.get(key, {}).get("name", key)
            elif kind == "state":
                name = STATE_NAMES.get(key, key)
            else:
                name = glossary.get((kind, key), {}).get("term", key)
            out.append({"kind": kind, "key": key, "name": name, "count": count})
    return out


# =============================================================================
# 2. The fact set — everything the model is allowed to know
# =============================================================================


def build_facts(target: dict[str, Any], producers: list[dict[str, Any]]) -> str:
    """The facts block for one target. See `on_page` for what is withheld.

    THIS IS THE WHOLE WORLD THE MODEL GETS. The prompt says anything not in the
    input does not go in the foreword, so what is assembled here decides what a
    foreword can truthfully say. Everything below comes from the hand-authored
    register or from published entries; nothing is inferred.
    """
    kind, key = target["kind"], target["key"]
    lines: list[str] = []

    if kind == "region":
        region = next((r for r in ts_data.regions() if r["slug"] == key), {})
        members = [p for p in producers if key in (p.get("regions") or [])]
        lines.append(f"Registered with Wine Australia as: {region.get('registered_as', 'unknown')}")
        if region.get("zone"):
            lines.append(f"GI zone: {region['zone']}")
        lines.append(f"State(s): {', '.join(STATE_NAMES.get(s, s) for s in region.get('states', []))}")
        if region.get("towns"):
            lines.append(f"Towns in the region: {', '.join(region['towns'])}")
        subs = [
            s for s in ts_data.subregions() if s["region"] == key
        ]
        if subs:
            registered = [s["name"] for s in subs if s.get("registered")]
            unregistered = [s["name"] for s in subs if not s.get("registered")]
            if registered:
                lines.append(f"Registered sub-regions: {', '.join(registered)}")
            if unregistered:
                lines.append(
                    f"Districts in common trade use, NOT registered: {', '.join(unregistered)}"
                )
        lines.append(_varieties_line(members))

    elif kind == "subregion":
        sub = next((s for s in ts_data.subregions() if s["slug"] == key), {})
        parent = next((r for r in ts_data.regions() if r["slug"] == sub.get("region")), {})
        members = [p for p in producers if key in (p.get("subregions") or [])]
        lines.append(f"Parent region: {parent.get('name', sub.get('region'))}")
        lines.append(
            "Registered as a GI sub-region: "
            + ("yes" if sub.get("registered") else "NO, it is in common trade use only")
        )
        if not sub.get("registered"):
            lines.append(
                f"A wine from here is labelled {parent.get('name', sub.get('region'))}."
            )
        if sub.get("towns"):
            lines.append(f"Towns: {', '.join(sub['towns'])}")
        lines.append(_varieties_line(members))

    elif kind == "state":
        members = [p for p in producers if p.get("state") == key]
        in_state = sorted(
            {region for p in members for region in (p.get("regions") or [])}
        )
        names = {r["slug"]: r["name"] for r in ts_data.regions()}
        all_regions = [r["name"] for r in ts_data.regions() if key in r.get("states", [])]
        lines.append(f"Wine regions registered in this state: {', '.join(all_regions)}")
        lines.append(
            "Regions this guide currently documents here: "
            + (", ".join(names.get(s, s) for s in in_state) or "none yet")
        )
        lines.append(_varieties_line(members))

    else:  # variety, practice
        entry = next(
            (e for e in ts_data.glossary() if e["vocabulary"] == kind and e["value"] == key),
            {},
        )
        if entry.get("aliases"):
            lines.append(f"Also called: {', '.join(entry['aliases'])}")
        if kind == "variety":
            members = [p for p in producers if key in (p.get("varieties") or [])]
        else:
            members = [
                p for p in producers if (p.get("practices") or {}).get(key) is True
            ]
        regions_here = sorted({r for p in members for r in (p.get("regions") or [])})
        names = {r["slug"]: r["name"] for r in ts_data.regions()}
        if regions_here:
            lines.append(
                "Regions where this guide documents it: "
                + ", ".join(names.get(s, s) for s in regions_here)
            )

    return "\n".join(line for line in lines if line)


def on_page(target: dict[str, Any]) -> str:
    """The prose the PAGE already renders around the foreword.

    DESIGN.md §7, on variety pages: the glossary definition "sits at the foot,
    linked, NOT DUPLICATED". The first generation broke that, because
    `build_facts` handed the model the register note and the glossary definition
    as source material and the page then printed those same sources a few
    centimetres away. Measured overlap reached 75% on the Adelaide Hills region
    and 64% on Cabernet Sauvignon, and the wild-ferment page said the same thing
    four times over.

    So these strings are no longer facts. They are shown to the model under a
    heading that tells it they are ALREADY ON THE PAGE and are there so it can
    avoid them. The foreword's job is what the definition cannot do: where this
    guide documents the thing, and how the register treats it.
    """
    kind, key = target["kind"], target["key"]
    lines: list[str] = []

    if kind == "region":
        region = next((r for r in ts_data.regions() if r["slug"] == key), {})
        if region.get("note"):
            lines.append(region["note"])
    elif kind == "subregion":
        sub = next((s for s in ts_data.subregions() if s["slug"] == key), {})
        parent = next((r for r in ts_data.regions() if r["slug"] == sub.get("region")), {})
        if not sub.get("registered"):
            lines.append(
                f"{sub.get('name', key)} is in common use in the wine trade and is "
                f"not on Wine Australia's register of Geographical Indications. "
                f"A wine from here is labelled {parent.get('name', '')}."
            )
        if sub.get("note"):
            lines.append(sub["note"])
    elif kind in ("variety", "practice"):
        entry = next(
            (e for e in ts_data.glossary() if e["vocabulary"] == kind and e["value"] == key),
            {},
        )
        # The variety page renders `short`; the practice page renders
        # `definition` and `excludes`. All three are withheld from the facts for
        # both, because `short` is a condensation of `definition` and a foreword
        # that paraphrases one paraphrases the other.
        for field in ("short", "definition", "excludes"):
            if entry.get(field):
                lines.append(entry[field])
        if kind == "practice":
            lines.append(
                "Every producer listed here states this in their own published "
                "material. Nothing on this page is an audit, an inspection or a "
                "certification. A producer who does not appear has not said "
                "otherwise, only that their published material does not say."
            )

    return "\n".join(f"- {line}" for line in lines) if lines else "- (nothing)"


def _varieties_line(members: list[dict[str, Any]]) -> str:
    varieties = sorted({v for p in members for v in (p.get("varieties") or [])})
    if not varieties:
        return "Varieties named by published entries: none stated."
    return f"Varieties named by published entries: {', '.join(varieties)}"


# =============================================================================
# 3. Validation — the contract the one re-ask is given
# =============================================================================


def _validate(text: str) -> str:
    """Return the cleaned paragraph, or raise ValueError with an actionable message."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise ValueError("the response was empty")

    if cleaned.startswith("#") or "```" in text:
        raise ValueError("return the paragraph as plain text, with no heading and no code fence")

    if "\n\n" in text.strip():
        raise ValueError("return ONE paragraph, not several")

    # TRUNCATION. The first run at max_tokens=1000 cut the Victoria foreword off
    # mid-sentence, on the word "The", and it was WRITTEN: the sentence counter
    # splits on terminal punctuation, so a trailing fragment carrying none is
    # not counted and the remaining sentences were in range. Prose that stops
    # dead is the one defect a reader notices instantly and no other rule here
    # catches.
    if not cleaned.endswith((".", "!", "?", '."', ".'", '?"', '!"')):
        raise ValueError(
            "the text ends mid-sentence, without terminal punctuation. "
            "Write a complete final sentence"
        )

    sentences = [s for s in cleaned.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if len(sentences) < MIN_SENTENCES:
        raise ValueError(
            f"the foreword has {len(sentences)} sentence(s); write {MIN_SENTENCES} to {MAX_SENTENCES}"
        )
    if len(sentences) > MAX_SENTENCES:
        raise ValueError(
            f"the foreword has {len(sentences)} sentences; write no more than {MAX_SENTENCES}"
        )

    # The same lists the Gatekeeper is run with. No second copy.
    hits = lint_text(cleaned, load_lists())
    if hits:
        detail = "; ".join(f"{hit['kind']}: {hit['phrase']}" for hit in hits[:6])
        raise ValueError(f"the draft uses banned register ({detail}). Rewrite without it")

    return cleaned


# =============================================================================
# 4. Generation
# =============================================================================


def load(path: Path = FOREWORDS_JSON_PATH) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {kind: {} for kind in KINDS}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: dict(data.get(kind, {})) for kind in KINDS}


def save(data: dict[str, dict[str, str]], path: Path = FOREWORDS_JSON_PATH) -> None:
    """Sorted keys, fixed separators, trailing newline — byte-stable between runs."""
    ordered = {kind: dict(sorted(data.get(kind, {}).items())) for kind in KINDS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ordered, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def generate(
    *,
    only: str | None = None,
    force: bool = False,
    log: Logger = lambda level, message: print(f"[{level}] {message}"),
    client: Any = None,
    path: Path = FOREWORDS_JSON_PATH,
) -> tuple[int, int]:
    """Draft every missing foreword. Returns ``(written, failed)``.

    Per-item failure is caught and logged, never raised: one region that fails
    must not cost the other seventy (UX.md §1.5 row 19).
    """
    producers = _published()
    existing = load(path)
    ledger = Ledger()

    pending = [
        target
        for target in targets(producers)
        if (only is None or f"{target['kind']}:{target['key']}" == only or target["key"] == only)
        and (force or not existing.get(target["kind"], {}).get(target["key"]))
    ]

    if not pending:
        log("info", "no forewords to write; every present page already has one")
        return (0, 0)

    written = failed = 0
    for target in pending:
        label = f"{target['kind']}/{target['key']}"
        try:
            prompt = load_prompt(
                "foreword",
                KIND=target["kind"],
                NAME=target["name"],
                COUNT=target["count"],
                FACTS=build_facts(target, producers),
                ON_PAGE=on_page(target),
            )
            text = call(
                "foreword",
                MODEL_FOREWORD,
                prompt,
                validate=_validate,
                log=log,
                ledger=ledger,
                slug=label,
                max_tokens=2000,
                client=client,
            )
        except (AgentError, MalformedOutput) as exc:
            # Non-fatal. The page renders without a foreword.
            log("warn", f"{label}: foreword not written ({exc})")
            failed += 1
            continue

        existing.setdefault(target["kind"], {})[target["key"]] = text
        written += 1
        log("info", f"{label}: {text[:70]}...")

    save(existing, path)
    log("info", f"wrote {written} foreword(s), {failed} failed")
    return (written, failed)


# =============================================================================
# 5. Self-test
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    errors: list[str] = []

    good = (
        "The Adelaide Hills is a registered wine region in the Mount Lofty Ranges "
        "zone of South Australia. Its vineyards sit above the plain around "
        "Lenswood and Piccadilly Valley. This guide documents chardonnay and "
        "pinot noir from producers there."
    )
    try:
        if _validate(good) != " ".join(good.split()):
            errors.append("selftest: a clean foreword was altered by the validator")
    except ValueError as exc:
        errors.append(f"selftest: a clean foreword was rejected: {exc}")

    cases = [
        ("", "empty response"),
        ("One sentence only.", "too few sentences"),
        (
            "It is a registered region in South Australia. Of those, the guide "
            "documents one. The",
            "a truncated final fragment",
        ),
        ("A. B. C. D. E. F. G.", "too many sentences"),
        ("# Heading\n\nTwo. Sentences.", "a heading"),
        (
            "The region is renowned for its wines. It is a must-visit destination.",
            "banned marketing words",
        ),
        (
            "It is a registered region in South Australia. The wines show notes of "
            "citrus on the palate.",
            "a tasting descriptor",
        ),
        (
            "It is a registered region. It is not just a name on a label.",
            "the not-X-but-Y construction",
        ),
        (
            "It is a registered region in South Australia. The vineyards are "
            "arguably the coolest in the state.",
            "a hedge word",
        ),
        (
            "It is a registered region. The wines have a distinctive colour \u2014 "
            "or rather color.",
            "an em dash and a US spelling",
        ),
    ]
    for text, why in cases:
        try:
            _validate(text)
        except ValueError:
            continue
        errors.append(f"selftest: the validator ACCEPTED a draft with {why}: {text!r}")

    # `targets` must mirror present-only membership.
    fixture = [
        {
            "slug": "a",
            "state": "SA",
            "regions": ["adelaide-hills"],
            "subregions": ["piccadilly-valley"],
            "varieties": ["chardonnay"],
            "practices": {"wild_ferment": True, "unfined": False},
        }
    ]
    got = {(t["kind"], t["key"]) for t in targets(fixture)}
    for expected in [
        ("region", "adelaide-hills"),
        ("subregion", "piccadilly-valley"),
        ("state", "SA"),
        ("variety", "chardonnay"),
        ("practice", "wild_ferment"),
    ]:
        if expected not in got:
            errors.append(f"selftest: targets() missed {expected}")
    if ("practice", "unfined") in got:
        errors.append("selftest: targets() included a practice flagged FALSE")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft aggregation-page forewords.")
    parser.add_argument("--generate", action="store_true", help="write missing forewords")
    parser.add_argument("--only", help="one key, e.g. adelaide-hills or region:adelaide-hills")
    parser.add_argument("--force", action="store_true", help="rewrite even if one exists")
    parser.add_argument("--list", action="store_true", help="show what needs one")
    args = parser.parse_args()

    errors = _selftest()
    if errors:
        print("FOREWORDS FAIL")
        for error in errors:
            print(f"  {error}")
        return 1

    if args.list or not args.generate:
        existing = load()
        rows = targets()
        missing = [t for t in rows if not existing.get(t["kind"], {}).get(t["key"])]
        print(f"FOREWORDS — selftest ok; {len(rows)} present page(s), {len(missing)} without a foreword")
        for target in missing:
            print(f"  {target['kind']}/{target['key']}  ({target['count']} producer(s))")
        return 0

    written, failed = generate(only=args.only, force=args.force)
    print(f"FOREWORDS — {written} written, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
