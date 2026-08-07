"""images.py — candidate photographs, and the separate publish action. Gate 5.

UX.md §4.

── The posture, which is the whole design ────────────────────────────────────

**Pages are designed to be complete with zero images.** Scraped photographs are
a staging convenience and an opt-in enhancement, never auto-published. A
label-only producer with no photograph is a normal entry and the interface never
suggests otherwise: no placeholder frame, no nagging, no different sort order.

So this module downloads candidates into gitignored `temp_data/` and stops.
Nothing here publishes anything without a separate, deliberate operator action.

── Publishing an image is one write, not two ─────────────────────────────────

`publish_image` sets the three frontmatter fields **and** inserts the
`<TippedPhoto>` tag into the body in the same write, because the producer page
renders a photograph exclusively from the body tag (UX.md §4 step 3). Setting
the fields alone produces a file that claims an image and shows none. The two
halves are one action, always, and `remove_image` is its exact reverse.

── Why candidates are restricted to the producer's own domain ────────────────

The reviewer's judgement at the thumbnail strip is "did this come from the
producer's own site?", and UX.md §4 step 2 requires the source URL to be visible
so they can make it. Downloading a regional tourism board's photograph in the
first place would put the burden on that one glance, every time, forever. It is
cheaper and safer to never fetch it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    HARVEST_USER_AGENT,
    HTTP_TIMEOUT_SECONDS,
    IMAGES_DIR,
    MAX_CANDIDATE_IMAGES,
    PUBLIC_IMAGES_DIR,
    PUBLISHED_DIR,
    PUBLISHED_IMAGE_MAX_PX,
    STAGING_DIR,
)
from admin.schema import read_mdx, write_mdx  # noqa: E402

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    pass


# =============================================================================
# 1. Finding candidates in the fetched HTML
# =============================================================================

_IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_SRCSET = re.compile(r"\bsrcset\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_OG_IMAGE = re.compile(
    r"<meta\b[^>]*?\bproperty\s*=\s*[\"']og:image[\"'][^>]*?\bcontent\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

#: Extensions worth a producer photograph. SVG and GIF are logos and spinners;
#: ICO is a favicon.
_USABLE = (".jpg", ".jpeg", ".png", ".webp")

#: Filename tells for furniture rather than photography. Cheap, and it keeps the
#: strip readable: six candidates the reviewer looks at beats six logos.
_FURNITURE = re.compile(
    r"(logo|icon|sprite|favicon|placeholder|spacer|pixel|avatar|badge|button"
    r"|banner|header|footer|cart|arrow|social|payment|visa|mastercard|paypal)",
    re.IGNORECASE,
)


def _registrable(host: str) -> str:
    """`shop.example.com.au` -> `example.com.au`. Good enough to compare sites."""
    parts = [part for part in host.lower().split(".") if part]
    if len(parts) <= 2:
        return ".".join(parts)
    # Australian domains are mostly three-label public suffixes (com.au).
    if parts[-1] == "au" and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


#: Asset hosts belonging to website builders and shop platforms.
#:
#: MEASURED, not anticipated. Basket Range Wine (SEED.md row 4) serves every
#: photograph on its own site from `images.squarespace-cdn.com`, so a strict
#: registrable-domain test returns ZERO candidates for it, and would for most of
#: a corpus of small producers: a site builder is what a two-person winery uses.
#:
#: Reading "the producer's own site" (UX.md §4 step 1) to include the CDN that
#: site is built on is the substance of the rule rather than its letter. The
#: protection UX.md §4 step 2 actually describes is preserved intact, because
#: what protects the reviewer is the SOURCE URL BEING VISIBLE on the thumbnail,
#: not the host having been filtered: a tourism board's photograph hotlinked
#: into a producer's page still has the tourism board's host and is still
#: excluded here, and anything that does get through is shown with its origin.
_PLATFORM_HOSTS = (
    "squarespace-cdn.com",
    "squarespace.com",
    "shopify.com",
    "shopifycdn.com",
    "wixstatic.com",
    "wixmp.com",
    "wpengine.com",
    "wp.com",
    "cloudfront.net",
    "bigcommerce.com",
    "webflow.com",
    "weebly.com",
    "godaddysites.com",
    "myshopify.com",
)


def _same_site(candidate: str, base: str) -> bool:
    host = urlparse(candidate).netloc.lower()
    left = _registrable(host)
    right = _registrable(urlparse(base).netloc)
    if left and left == right:
        return True
    return any(host == platform or host.endswith("." + platform) for platform in _PLATFORM_HOSTS)


def candidate_urls(html: str, base_url: str) -> list[str]:
    """Absolute, deduplicated, same-site image URLs, in page order."""
    found: list[str] = []

    for match in _OG_IMAGE.finditer(html):
        found.append(match.group(1))
    for match in _IMG_SRC.finditer(html):
        found.append(match.group(1))
    for match in _SRCSET.finditer(html):
        # `a.jpg 480w, b.jpg 960w` — take the largest declared width last.
        for part in match.group(1).split(","):
            url = part.strip().split(" ")[0]
            if url:
                found.append(url)

    seen: set[str] = set()
    out: list[str] = []
    for raw in found:
        raw = raw.strip()
        if not raw or raw.startswith("data:"):
            continue
        absolute = urljoin(base_url, raw)
        if not absolute.lower().startswith(("http://", "https://")):
            continue
        path = urlparse(absolute).path
        if not path.lower().endswith(_USABLE):
            continue
        if _FURNITURE.search(path):
            continue
        if not _same_site(absolute, base_url):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
    return out


# =============================================================================
# 2. Downloading them
# =============================================================================

#: Below this on either edge it is furniture, whatever it is called.
MIN_CANDIDATE_PX = 500


def candidate_dir(slug: str) -> Path:
    return IMAGES_DIR / slug


def manifest_path(slug: str) -> Path:
    return candidate_dir(slug) / "manifest.json"


def read_manifest(slug: str) -> dict[str, Any]:
    path = manifest_path(slug)
    if not path.is_file():
        return {"slug": slug, "images": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"slug": slug, "images": []}
    if not isinstance(data, dict):
        return {"slug": slug, "images": []}
    data.setdefault("slug", slug)
    data.setdefault("images", [])
    return data


def download_candidates(
    slug: str,
    html: str,
    base_url: str,
    *,
    log: Logger = _null_log,
    limit: int = MAX_CANDIDATE_IMAGES,
) -> list[dict[str, Any]]:
    """Download up to `limit` candidates into `temp_data/images/<slug>/`.

    UX.md §1.5 row 21: a failed download is warned per image and is never fatal.
    Approving with no image at all is the normal path.
    """
    import httpx
    from PIL import Image, UnidentifiedImageError

    urls = candidate_urls(html, base_url)
    if not urls:
        log("info", "no candidate images found on the page")
        return []

    directory = candidate_dir(slug)
    directory.mkdir(parents=True, exist_ok=True)

    images: list[dict[str, Any]] = []
    with httpx.Client(
        headers={"User-Agent": HARVEST_USER_AGENT},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        for url in urls:
            if len(images) >= limit:
                break
            try:
                response = client.get(url)
                if response.status_code != 200:
                    log("warn", f"candidate image HTTP {response.status_code}: {url}")
                    continue
                suffix = Path(urlparse(url).path).suffix.lower() or ".jpg"
                name = f"{len(images):02d}{suffix}"
                target = directory / name
                target.write_bytes(response.content)

                try:
                    with Image.open(target) as opened:
                        width, height = opened.size
                except (UnidentifiedImageError, OSError) as exc:
                    log("warn", f"candidate image unreadable ({exc}): {url}")
                    target.unlink(missing_ok=True)
                    continue

                if width < MIN_CANDIDATE_PX or height < MIN_CANDIDATE_PX:
                    target.unlink(missing_ok=True)
                    continue

                images.append(
                    {
                        "file": name,
                        "source_url": url,
                        "width": width,
                        "height": height,
                        "bytes": len(response.content),
                    }
                )
            except Exception as exc:
                log("warn", f"candidate image failed ({type(exc).__name__}): {url}")

    manifest = {"slug": slug, "base_url": base_url, "images": images}
    manifest_path(slug).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if images:
        log(
            "info",
            f"downloaded {len(images)} candidate image"
            f"{'' if len(images) == 1 else 's'} to "
            f"{IMAGES_DIR.name}/{slug}/",
        )
    else:
        log("info", "no usable candidate images (all were furniture or too small)")
    return images


# =============================================================================
# 3. The body tag
#
# UX.md §4 step 3. The producer page renders a photograph exclusively from this
# tag; the frontmatter fields carry the data the tag and the metadata need.
# =============================================================================

TIPPED_PHOTO = re.compile(r"\n*<TippedPhoto\b.*?/>\n*|\n*<TippedPhoto\b.*?</TippedPhoto>\n*", re.DOTALL)


def _escape(value: str) -> str:
    return str(value).replace('"', "&quot;")


def build_tag(src: str, caption: str, source: str, alt: str = "") -> str:
    attributes = [f'src="{_escape(src)}"', f'caption="{_escape(caption)}"', f'source="{_escape(source)}"']
    if alt:
        attributes.append(f'alt="{_escape(alt)}"')
    return "<TippedPhoto\n  " + "\n  ".join(attributes) + "\n/>"


def strip_tag(body: str) -> str:
    return TIPPED_PHOTO.sub("\n\n", body).strip() + "\n"


def insert_tag(body: str, tag: str) -> str:
    """Place the plate MID-ARTICLE, never at the top (DESIGN.md §4).

    Splits on blank lines and inserts after the paragraph nearest the middle, so
    the photograph sits inside the prose rather than heading it or trailing it.
    """
    body = strip_tag(body)
    blocks = [block for block in re.split(r"\n\s*\n", body) if block.strip()]
    if len(blocks) < 2:
        return (body.rstrip() + "\n\n" + tag + "\n") if body.strip() else tag + "\n"
    # An MDX comment block at the top is not a paragraph; do not count it.
    first_prose = 0
    while first_prose < len(blocks) and blocks[first_prose].lstrip().startswith("{/*"):
        first_prose += 1
    middle = first_prose + max(1, (len(blocks) - first_prose) // 2)
    middle = min(middle, len(blocks))
    out = blocks[:middle] + [tag] + blocks[middle:]
    return "\n\n".join(out).strip() + "\n"


# =============================================================================
# 4. Publish and remove
# =============================================================================


def suggest_caption(data: dict[str, Any]) -> str:
    """A starting point in the register, for the reviewer to edit.

    `LOT I. — THE HOME BLOCK, LOOKING WEST.` is the full register. A bearing
    nobody published is not invented, so the suggestion stops at what is known:
    the suburb, when there is one.
    """
    suburb = str((data.get("location") or {}).get("suburb") or "").strip()
    if suburb:
        return f"LOT I. — {suburb.upper()}."
    return "LOT I."


def _draft_path(slug: str, directory: Path) -> Path:
    return directory / f"{slug}.mdx"


def published_asset(slug: str) -> Path:
    return PUBLIC_IMAGES_DIR / f"{slug}.webp"


def publish_image(
    slug: str,
    filename: str,
    *,
    caption: str,
    alt: str = "",
    directory: Path = STAGING_DIR,
    log: Logger = _null_log,
) -> dict[str, Any]:
    """Resize to webp, write the three fields AND the body tag, in one write.

    Works on a staged draft or an already-published producer (UX.md §4 step 4).
    """
    from PIL import Image

    source = candidate_dir(slug) / filename
    if not source.is_file():
        raise FileNotFoundError(f"candidate image not found: {slug}/{filename}")

    manifest = read_manifest(slug)
    record = next((row for row in manifest.get("images", []) if row.get("file") == filename), None)
    if record is None:
        raise ValueError(f"{filename} is not in the manifest for {slug}")
    source_url = record["source_url"]

    caption = str(caption or "").strip()
    if not caption:
        raise ValueError("image_caption is required (SCHEMA.md §2a rule 1)")

    path = _draft_path(slug, directory)
    if not path.is_file():
        raise FileNotFoundError(f"no entry at {path}")
    data, body = read_mdx(path)

    PUBLIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    target = published_asset(slug)
    with Image.open(source) as opened:
        opened = opened.convert("RGB")
        opened.thumbnail(
            (PUBLISHED_IMAGE_MAX_PX, PUBLISHED_IMAGE_MAX_PX), Image.LANCZOS
        )
        # 76 rather than the 82 this was written with. Measured on a real
        # 2500x1667 producer photograph at the 1600px long edge: 82 gives 551 kB
        # and 76 gives 444 kB, for a difference no reader sees on one inset
        # plate. `method=6` is the slowest, smallest encoder setting, which is
        # the right trade when an image is encoded once and served forever.
        opened.save(target, "WEBP", quality=76, method=6)

    public_path = f"/images/{slug}.webp"
    data["image"] = public_path
    data["image_source"] = source_url
    data["image_caption"] = caption

    body = insert_tag(body, build_tag(public_path, caption, source_url, alt))
    write_mdx(path, data, body)

    log(
        "info",
        f"published image {target.name} ({target.stat().st_size // 1024} kB) "
        f"and inserted the body tag",
    )
    return {"image": public_path, "image_source": source_url, "image_caption": caption}


def remove_image(
    slug: str,
    *,
    directory: Path | None = None,
    log: Logger = _null_log,
) -> dict[str, Any]:
    """The exact reverse: three fields dropped, body tag stripped, asset deleted.

    `directory` defaults to wherever the entry actually is, so a takedown is one
    action whether the producer is staged or published (UX.md §4 step 4).
    """
    if directory is None:
        directory = STAGING_DIR if _draft_path(slug, STAGING_DIR).is_file() else PUBLISHED_DIR

    path = _draft_path(slug, directory)
    if not path.is_file():
        raise FileNotFoundError(f"no entry at {path}")

    data, body = read_mdx(path)
    for field in ("image", "image_source", "image_caption"):
        data.pop(field, None)
    write_mdx(path, data, strip_tag(body))

    asset = published_asset(slug)
    existed = asset.is_file()
    asset.unlink(missing_ok=True)

    log("info", f"removed the image from {slug}" + (" and deleted the asset" if existed else ""))
    return {"asset_deleted": existed}
