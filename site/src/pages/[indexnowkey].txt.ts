import type { APIRoute } from "astro";

/**
 * The IndexNow key verification file.
 *
 * `deploy.py` declares `keyLocation` as `{SITE_URL}/{key}.txt` on every ping,
 * and the IndexNow endpoint rejects a submission whose key file it cannot read
 * and match. This route is that file, and without it the ping is refused no
 * matter how correct the key is.
 *
 * ── Why this is generated and not a file in `site/public/` ──────────────────
 *
 * `site/public/` is outside the deploy's `ALLOWED_PREFIXES` — only
 * `site/public/images/` and `site/public/blog-images/` are legal — so a key
 * parked there would be refused by the guard as an unexpected path. Widening
 * the allow-list to let it through would weaken the guard and commit a token
 * to version control in the same change. Emitting the file at build time keeps
 * both properties: Netlify serves it out of `dist/`, and git never sees it.
 *
 * ── Failing closed ─────────────────────────────────────────────────────────
 *
 * No key set means no route: `getStaticPaths` returns nothing and the build
 * emits nothing. `deploy.py` skips the ping under the same condition, so the
 * two halves are never live one at a time — either the key file is served and
 * the ping fires, or neither happens.
 *
 * **The key must be set in Netlify's own build environment**, not only in the
 * local `.env`. `.env` is read by the admin, and Netlify builds from the pushed
 * repository, which never contains it. A key present locally and absent on
 * Netlify produces a ping whose `keyLocation` is a 404.
 */

/** Astro resolves static routes ahead of dynamic ones, so a future `llms.txt`
 * at Gate 10 takes precedence over this catch-all without any change here. */
export function getStaticPaths() {
  const key = (process.env.INDEXNOW_KEY ?? "").trim();
  return key ? [{ params: { indexnowkey: key } }] : [];
}

/** IndexNow requires the body to be the key and nothing else. */
export const GET: APIRoute = ({ params }) =>
  new Response(params.indexnowkey, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
