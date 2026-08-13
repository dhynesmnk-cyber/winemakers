"""blog_images.py — images for a post, uploaded on insert. UX.md §6, Gate 11.

UX.md §6: "In-body images upload immediately on insert and return their URL.
There is no separate publish-image step for blog images, because a post's images
are part of the authored draft rather than harvested candidates needing a
curation decision. This is deliberately different from §4, which is
producer-specific."

That is the whole design in one paragraph, and it is why this module is not a
branch of `images.py`. There are no candidates, no manifest, no source URL to
attribute an in-body image to, and no separate publish action. A post's image
arrives from the author's disk, is encoded once, and has a URL immediately.

── Why base64 in a JSON body, and not a file upload ─────────────────────────

FastAPI needs `python-multipart` for `UploadFile`, and TRD.md §2.2 lists it
among the dependencies this project deliberately does not carry. Adding one
would be a CLAUDE.md rule 2 question for the sake of a transport detail, so the
browser reads the file and posts base64 in the JSON body every other route here
already speaks. Pillow is pinned and already does exactly this encode for
producer photographs.

The cost is roughly a third more bytes on the wire, over localhost, once per
image. The benefit is that the dependency list does not move.

── Where the files go, and why the slug is in the path ──────────────────────

    staged:    content-staging/_blog_staging/_images/<slug>/<name>.webp
    published: site/public/blog-images/<slug>/<name>.webp

Under the post's own directory, both sides. The publish move used to flatten
this, copying `_images/<slug>/cover.webp` to `blog-images/cover.webp`, so two
posts each carrying a `cover` silently overwrote one another and the body's
rewritten URL pointed at a path that no longer existed. The slug segment is what
makes an image belong to a post rather than to a filename.

`site/public/blog-images/` is a PREFIX on the deploy allow-list (TRD.md §6.5),
so the nested path is already legal and `deploy.py` needs no change.

── A name is never silently reused ──────────────────────────────────────────

Two different photographs called `photo.jpg` in one post are uniquified to
`photo.webp` and `photo-2.webp` rather than the second replacing the first. The
same photograph uploaded twice therefore lands twice, which is visible and
harmless; overwriting would silently change an image the published body already
points at, which is neither.
"""

from __future__ import annotations

import base64
import binascii
import re
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import PUBLISHED_IMAGE_MAX_PX  # noqa: E402
from admin.pipeline import blog  # noqa: E402
from admin.pipeline.images import WEBP_METHOD, WEBP_QUALITY  # noqa: E402

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    """Default logger. The store is usable from a CLI with no log pane."""


#: The public URL roots. These are what the ADMIN mounts and what the SITE
#: serves, deliberately spelled the same on both sides: a preview that resolved
#: an image by a different path from the shipped page would render correctly for
#: the reviewer and 404 for the reader, which is the shape of defect this
#: project has the least tolerance for.
PUBLISHED_URL_ROOT = "/blog-images"
STAGING_URL_ROOT = "/blog-staging-images"

#: A ceiling on the DECODED bytes. A photograph straight off a camera is a few
#: megabytes; this is generous for that and still refuses a paste that would sit
#: in the admin's memory. Checked after decoding, because the base64 length is
#: not the thing that costs.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

#: `data:image/jpeg;base64,....` — the browser's `FileReader.readAsDataURL`
#: prefix, accepted so the client can post what it already has.
_DATA_URL = re.compile(r"^data:[^;,]*;base64,", re.IGNORECASE)


class UploadError(ValueError):
    """The upload cannot be stored, with a reason for the author to act on."""


def _guard(slug: str) -> str:
    """Refuse anything that is not a bare kebab-case slug.

    The same guard `blog._guard` applies, for the same reason: this joins the
    slug to a directory and the value arrives from an HTTP route.
    """
    if not blog.is_slug(slug):
        raise UploadError(f"not a valid post slug: {slug!r}")
    return slug


def directory_for(slug: str, *, published: bool) -> Path:
    root = blog.BLOG_IMAGES_DIR if published else blog.BLOG_STAGING_IMAGES_DIR
    return root / _guard(slug)


def url_for(slug: str, name: str, *, published: bool) -> str:
    root = PUBLISHED_URL_ROOT if published else STAGING_URL_ROOT
    return f"{root}/{_guard(slug)}/{name}"


def asset_name(filename: str) -> str:
    """`Home Block, looking west.JPG` -> `home-block-looking-west.webp`.

    Through `blog.slugify`, so a filename cannot carry a path separator, a
    leading dot or a space into a URL. Everything is webp because everything is
    re-encoded.
    """
    return f"{blog.slugify(Path(filename or '').stem)}.webp"


def _free_path(directory: Path, name: str) -> Path:
    """`photo.webp`, then `photo-2.webp`, then `photo-3.webp`.

    See the module note: a published body may already point at the name being
    reused, so the existing file is never overwritten.
    """
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    for index in range(2, 1000):
        candidate = directory / f"{stem}-{index}.webp"
        if not candidate.exists():
            return candidate
    raise UploadError(f"too many images named {name!r} in this post")


def decode(payload: str) -> bytes:
    """Base64 (bare, or as a data URL) to bytes, with the size ceiling applied."""
    text = _DATA_URL.sub("", (payload or "").strip())
    if not text:
        raise UploadError("the upload carried no image data")
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise UploadError(f"the upload is not valid base64: {exc}") from exc
    if not raw:
        raise UploadError("the upload decoded to nothing")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UploadError(
            f"the image is {len(raw) // 1024 // 1024} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB. Export it smaller and try again."
        )
    return raw


def store(
    slug: str,
    filename: str,
    raw: bytes,
    *,
    published: bool,
    log: Logger = _null_log,
) -> dict[str, Any]:
    """Encode one image into the post's directory. Returns its URL and size.

    `published` picks the destination, and the caller reads it off the post
    rather than passing a preference: UX.md §6 says a new image on an
    already-live post "goes straight to the published image directory, since the
    post is already live", and a staged one waits for the publish move.
    """
    from PIL import Image, UnidentifiedImageError

    import io

    directory = directory_for(slug, published=published)
    directory.mkdir(parents=True, exist_ok=True)
    target = _free_path(directory, asset_name(filename))

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            # RGB before webp for the same reason `images.publish_image` does
            # it: a CMYK JPEG or a palette PNG will not encode otherwise.
            opened = opened.convert("RGB")
            opened.thumbnail(
                (PUBLISHED_IMAGE_MAX_PX, PUBLISHED_IMAGE_MAX_PX), Image.LANCZOS
            )
            opened.save(target, "WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    except UnidentifiedImageError as exc:
        raise UploadError(
            f"{filename!r} is not an image Pillow can read ({exc})"
        ) from exc
    except OSError as exc:
        raise UploadError(f"{filename!r} could not be encoded: {exc}") from exc

    url = url_for(slug, target.name, published=published)
    size = target.stat().st_size
    log("info", f"blog: stored {url} ({size // 1024} kB)")
    return {"url": url, "name": target.name, "bytes": size, "published": published}


# =============================================================================
# Self-test — validate.md's pattern
# =============================================================================


def _selftest() -> list[str]:
    """Must catch a corrupted fixture and pass a clean one."""
    import io
    import tempfile

    errors: list[str] = []

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is pinned
        return ["selftest: Pillow is not importable, so nothing here was verified"]

    def png(colour: str = "red", size: tuple[int, int] = (40, 30)) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", size, colour).save(buffer, "PNG")
        return buffer.getvalue()

    # Names must survive into a URL without carrying a path or a space.
    for filename, expected in (
        ("Home Block, looking west.JPG", "home-block-looking-west.webp"),
        ("../../etc/passwd", "passwd.webp"),
        ("photo.jpeg", "photo.webp"),
        ("", "untitled.webp"),
    ):
        if asset_name(filename) != expected:
            errors.append(
                f"selftest: asset_name({filename!r}) gave {asset_name(filename)!r}, "
                f"expected {expected!r}"
            )

    for bad in ("../etc", "Who-Owns", "a_b", "/abs", ""):
        for call, why in (
            (lambda: directory_for(bad, published=False), "directory_for"),
            (lambda: url_for(bad, "x.webp", published=True), "url_for"),
        ):
            try:
                call()
            except UploadError:
                continue
            errors.append(f"selftest: {why} built a path from {bad!r}")

    # The decoder must refuse what it cannot use, and say why.
    for payload, why in (
        ("", "an empty payload"),
        ("not base64!!", "unparseable base64"),
        (base64.b64encode(b"x" * (MAX_UPLOAD_BYTES + 1)).decode(), "an oversized image"),
    ):
        try:
            decode(payload)
        except UploadError:
            continue
        errors.append(f"selftest: decode ACCEPTED {why}")

    if decode(f"data:image/png;base64,{base64.b64encode(png()).decode()}") != png():
        errors.append("selftest: a data-URL prefix was not stripped")

    real_staging, real_published = blog.BLOG_STAGING_IMAGES_DIR, blog.BLOG_IMAGES_DIR
    with tempfile.TemporaryDirectory() as tmp:
        try:
            blog.BLOG_STAGING_IMAGES_DIR = Path(tmp) / "staged"
            blog.BLOG_IMAGES_DIR = Path(tmp) / "published"

            first = store("post-one", "photo.jpg", png(), published=False)
            if first["url"] != "/blog-staging-images/post-one/photo.webp":
                errors.append(f"selftest: a staged upload returned {first['url']!r}")

            # THE COLLISION. Two posts, one filename. Before Gate 11's fix the
            # publish move flattened these onto each other.
            second = store("post-two", "photo.jpg", png("blue"), published=False)
            if second["url"] != "/blog-staging-images/post-two/photo.webp":
                errors.append(f"selftest: a second post's upload returned {second['url']!r}")
            if first["url"] == second["url"]:
                errors.append(
                    "selftest: two posts uploading one filename share a URL. That is "
                    "the collision the slug directory exists to prevent."
                )

            # And within ONE post, a repeated name is uniquified rather than
            # overwriting something the published body may already point at.
            again = store("post-one", "photo.jpg", png("green"), published=False)
            if again["name"] != "photo-2.webp":
                errors.append(
                    f"selftest: a repeated filename gave {again['name']!r}; it must "
                    f"not overwrite photo.webp"
                )

            live = store("post-one", "photo.jpg", png(), published=True)
            if live["url"] != "/blog-images/post-one/photo.webp":
                errors.append(f"selftest: a published upload returned {live['url']!r}")

            # The encode must actually produce a webp, downscaled to the ceiling.
            wide = store("post-one", "wide.jpg", png(size=(4000, 100)), published=True)
            path = Path(tmp) / "published" / "post-one" / wide["name"]
            with Image.open(path) as opened:
                if opened.format != "WEBP":
                    errors.append(f"selftest: stored a {opened.format}, not a WEBP")
                if opened.width > PUBLISHED_IMAGE_MAX_PX:
                    errors.append(
                        f"selftest: {opened.width}px wide, over the "
                        f"{PUBLISHED_IMAGE_MAX_PX}px ceiling"
                    )

            try:
                store("post-one", "notes.txt", b"this is not an image", published=False)
            except UploadError:
                pass
            else:
                errors.append("selftest: store ACCEPTED bytes that are not an image")
        finally:
            blog.BLOG_STAGING_IMAGES_DIR = real_staging
            blog.BLOG_IMAGES_DIR = real_published

    return errors


def main() -> int:
    errors = _selftest()
    if errors:
        print("BLOG IMAGES FAIL")
        for error in errors:
            print(f"  {error}")
        return 1
    print(
        f"BLOG IMAGES — selftest ok; webp q{WEBP_QUALITY} m{WEBP_METHOD} at "
        f"{PUBLISHED_IMAGE_MAX_PX}px, {MAX_UPLOAD_BYTES // 1024 // 1024} MB ceiling"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
