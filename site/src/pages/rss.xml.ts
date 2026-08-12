/**
 * `/rss.xml` — the journal's feed. AN ENDPOINT, NOT A STATIC FILE.
 *
 * Gate 11. `Footer.astro` has linked this since Gate 1 and no route table in
 * TRD.md, UX.md or DESIGN.md ever said what it should contain; the shape is
 * decided in TRD.md §3's 2026-08-13 amendment rather than improvised here.
 *
 * ── Summaries, not full bodies ────────────────────────────────────────────────
 *
 * `<description>` carries the post's `summary` and nothing else. A feed carrying
 * full bodies would be a second rendering of the same prose with no `<Figure>`
 * a reader could trust — every count would be frozen at the moment the feed was
 * fetched — and every amendment recorded by `updated` would be invisible to
 * anyone reading the copy in their reader. The summary plus a link sends the
 * reader to the version that stays right. Same reasoning as TRD.md §4.4's
 * refusal of runtime fetching, applied to the copy rather than to the data.
 *
 * ── No dependency ─────────────────────────────────────────────────────────────
 *
 * `@astrojs/rss` exists and is not installed (CLAUDE.md rule 2). RSS 2.0 is a
 * fixed shape of about twenty lines; a package for it would buy nothing and
 * would own the one file whose output a reader's software parses strictly.
 *
 * Escaping is the one thing worth care here: a post title carrying `&` or `<`
 * produces a feed that will not parse at all, and the reader who sees that sees
 * a broken feed rather than a broken title.
 */

import type { APIRoute } from "astro";

import { SITE_NAME, SITE_TAGLINE, SITE_URL } from "../config.ts";
import { allPosts, postHref } from "../data/posts.ts";

/** The five characters XML cannot carry raw. */
function escape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * RFC 822, which RSS 2.0 requires and `Date` has no built-in formatter for.
 *
 * Built from the UTC components deliberately. `published` is a date with no time
 * of day, so it parses as UTC midnight; formatting it in a local timezone would
 * move a post to the previous day for every reader west of Greenwich, and the
 * build machine's timezone would decide which.
 */
function rfc822(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${DAYS[date.getUTCDay()]}, ${pad(date.getUTCDate())} ` +
    `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()} ` +
    `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:` +
    `${pad(date.getUTCSeconds())} GMT`
  );
}

export const GET: APIRoute = async () => {
  const posts = await allPosts();

  const items = posts.map((post) => {
    const url = new URL(postHref(post.id), SITE_URL).href;
    return [
      "    <item>",
      `      <title>${escape(post.data.title)}</title>`,
      `      <link>${escape(url)}</link>`,
      `      <guid isPermaLink="true">${escape(url)}</guid>`,
      `      <pubDate>${rfc822(post.data.published)}</pubDate>`,
      `      <description>${escape(post.data.summary)}</description>`,
      "    </item>",
    ].join("\n");
  });

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    // Interpunct, not an em dash — the editorial guardrails apply to anything a
    // reader sees, and a feed title is read in somebody's reader.
    `    <title>${escape(`${SITE_NAME} · the journal`)}</title>`,
    `    <link>${escape(new URL("/blog/", SITE_URL).href)}</link>`,
    `    <description>${escape(SITE_TAGLINE)}</description>`,
    "    <language>en-AU</language>",
    `    <atom:link href="${escape(new URL("/rss.xml", SITE_URL).href)}" rel="self" type="application/rss+xml" />`,
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");

  return new Response(body, {
    headers: { "Content-Type": "application/rss+xml; charset=utf-8" },
  });
};
