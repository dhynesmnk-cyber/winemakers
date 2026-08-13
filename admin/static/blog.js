/*
  blog.js — the blog authoring screen. UX.md §6, Gate 11.

  Hand-written vanilla JS, no framework, no build step, no CDN (TRD.md §2.1).
  Same posture as admin.js and deliberately a separate file: the two screens
  share the log stream and nothing else, and one file serving both would be a
  file where a change to the producer editor can break the post editor.

  ── The body editor ─────────────────────────────────────────────────────────

  A textarea over the post's MDX source with a toolbar that writes markdown at
  the cursor, and a live preview beside it. Decided 2026-08-13 (TRD.md §2.5):
  WYSIWYG round-trips MDX through HTML, and <Pull>, <Figure> and images do not
  survive that trip. The toolbar is an accelerator over the source, never a
  layer above it.
*/

"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

/** Small element builder. Text goes in as text, never as innerHTML. */
function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(options)) {
    if (key === "text") node.textContent = value;
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

const state = {
  slug: null,
  frontmatter: {},
  body: "",
  published: false,
  factcheck: null,
  saveTimer: null,
  // True while the fact-check holds the post on the server. See `setLocked`.
  locked: false,
};

/* ── The log, shared with the hub ─────────────────────────────────────── */

function appendLog(line) {
  const pane = $("#log");
  // The hub's markup exactly: `.log li.level-X` with `.at` and `.prefix`. The
  // CSS is already written for it, and colour is never the only carrier of
  // level, so the prefix is text.
  pane.append(
    el("li", { class: `level-${line.level}` }, [
      el("span", { class: "at", text: line.at }),
      el("span", { class: "prefix", text: line.level }),
      el("span", { text: line.message }),
    ]),
  );
  while (pane.children.length > 500) pane.firstElementChild.remove();
  pane.scrollTop = pane.scrollHeight;
}

function startLog() {
  if (!("EventSource" in window)) {
    // Falls back to polling, per UX.md §1.2, exactly as the hub does.
    let seen = 0;
    setInterval(async () => {
      const data = await fetch("/api/log").then((r) => r.json());
      data.lines.slice(seen).forEach(appendLog);
      seen = data.lines.length;
    }, 3000);
    return;
  }
  const source = new EventSource("/events");
  source.onmessage = (event) => appendLog(JSON.parse(event.data));
}

/* ── The post list ────────────────────────────────────────────────────── */

async function refreshList() {
  const data = await fetch("/api/posts").then((r) => r.json());
  const list = $("#post-list");
  list.replaceChildren();

  if (data.rows.length === 0) {
    list.append(el("li", { class: "empty-state", text: "No posts yet. Start a draft to begin." }));
    return;
  }

  for (const row of data.rows) {
    const chipClass =
      row.unresolved > 0 ? "chip-blocked" : row.status === "published" ? "chip-published" : "";
    const button = el("button", { type: "button", class: "post-row", "data-slug": row.slug }, [
      el("span", { class: "post-row__title", text: row.title }),
      el("span", { class: `post-row__chip mono mono-caps ${chipClass}`, text: row.chip }),
      el("span", {
        class: "post-row__detail mono",
        text: [row.detail, row.published, `${row.words} words`].filter(Boolean).join(" · "),
      }),
    ]);
    if (row.slug === state.slug) button.classList.add("is-current");
    list.append(el("li", {}, [button]));
  }
}

document.addEventListener("click", (event) => {
  const row = event.target.closest(".post-row");
  if (row) open(row.dataset.slug);
});

/* ── Opening a post ───────────────────────────────────────────────────── */

async function open(slug) {
  const response = await fetch(`/api/post/${slug}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    window.alert(detail.detail || `Could not open ${slug}`);
    return;
  }
  const data = await response.json();

  state.slug = data.slug;
  state.frontmatter = data.frontmatter;
  state.body = data.body;
  state.published = data.published;
  state.factcheck = data.factcheck;

  $("#editor-empty").hidden = true;
  $("#editor").hidden = false;

  $("#f-title").value = data.frontmatter.title || "";
  $("#f-summary").value = data.frontmatter.summary || "";
  $("#f-dateline").value = data.frontmatter.dateline || "";
  $("#f-published").value = data.frontmatter.published || "";
  $("#f-cover").value = data.frontmatter.cover || "";
  $("#f-cover-source").value = data.frontmatter.cover_source || "";
  $("#f-cover-caption").value = data.frontmatter.cover_caption || "";
  $("#f-body").value = data.body;

  // UX.md §6: deleting an already-published post is not offered, and a
  // published post is fact-checked before it publishes rather than after.
  $("#delete").hidden = data.published;
  $("#publish").hidden = data.published;
  $("#factcheck").hidden = data.published;

  renderSources();
  renderClaims();
  renderBlocks(data.blocks);
  countWords();
  countSummary();
  reloadPreview();
  refreshList();

  // A run may already be in flight, started from another tab or before this
  // page was loaded. The server is the authority on that, not this tab.
  setLocked(
    Boolean(data.factchecking),
    "The fact-check is running on this post. The editor reopens on the checked " +
      "copy when it finishes.",
  );
}

/* ── The editor lock ──────────────────────────────────────────────────────
 *
 * The fact-check rewrites the staged body on the server while this textarea
 * stays live on a 600ms debounce. A keystroke during a run used to put the
 * pre-check body back over the corrected one, reinstating the sentences the
 * audit had just recorded as removed. The server refuses those saves with a
 * 409; this stops the author typing into a box whose contents are about to be
 * thrown away.
 *
 * The reason is printed, never implied. UX.md §5 counts a disabled control with
 * no stated cause as a UX bug against the specification.
 */
const LOCKABLE =
  "#f-title, #f-summary, #f-dateline, #f-published, #f-cover, #f-cover-source," +
  " #f-cover-caption, #f-body, #source-title, #source-url, #source-add," +
  " #factcheck, #publish, #delete, #cover-upload, .toolbar button";

function setLocked(locked, reason) {
  state.locked = locked;
  $$(LOCKABLE).forEach((node) => {
    node.disabled = locked;
  });
  const notice = $("#locked-notice");
  notice.hidden = !locked;
  notice.textContent = locked ? reason : "";
}

/* ── Autosave — the same 600ms debounce as the producer editor (UX.md §1.4) ── */

function queueSave() {
  if (state.locked) return;
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(save, 600);
}

async function save() {
  if (!state.slug) return;
  try {
    const response = await fetch(`/api/post/${state.slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frontmatter: state.frontmatter, body: state.body }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      setSaveState(`save failed: ${detail.detail || response.status}`, true);
      return;
    }
    const data = await response.json();
    setSaveState(`saved ${data.saved}`, false);
    renderBlocks(data.blocks);
    reloadPreview();
    refreshList();
  } catch (error) {
    setSaveState(`save failed: ${error.message}`, true);
  }
}

function setSaveState(text, failed) {
  const node = $("#save-state");
  node.textContent = text;
  node.classList.toggle("warn", Boolean(failed));
}

function bindField(selector, field) {
  $(selector).addEventListener("input", (event) => {
    const value = event.target.value;
    state.frontmatter[field] = value === "" ? null : value;
    queueSave();
  });
}

/* ── The body editor and its toolbar ──────────────────────────────────── */

$("#f-body").addEventListener("input", (event) => {
  state.body = event.target.value;
  countWords();
  queueSave();
});

/**
 * Insert at the cursor, keeping the selection sensible afterwards.
 *
 * `setRangeText` rather than rebuilding `value`, so the browser's own undo
 * stack survives. A toolbar that destroys undo is worse than no toolbar.
 */
function surround(before, after) {
  const area = $("#f-body");
  const { selectionStart: start, selectionEnd: end } = area;
  const selected = area.value.slice(start, end);
  area.setRangeText(`${before}${selected}${after}`, start, end, "end");
  if (start === end) {
    // Empty selection: put the caret between the markers so typing lands there.
    area.selectionStart = area.selectionEnd = start + before.length;
  }
  area.focus();
  area.dispatchEvent(new Event("input", { bubbles: true }));
}

function prefixLine(prefix) {
  const area = $("#f-body");
  const start = area.value.lastIndexOf("\n", area.selectionStart - 1) + 1;
  area.setRangeText(prefix, start, start, "end");
  area.focus();
  area.dispatchEvent(new Event("input", { bubbles: true }));
}

$$(".toolbar button").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.wrap) {
      surround(button.dataset.wrap, button.dataset.wrap);
    } else if (button.dataset.prefix) {
      prefixLine(button.dataset.prefix);
    } else if (button.dataset.link) {
      const url = window.prompt("Link URL");
      if (url) surround("[", `](${url})`);
    } else if (button.dataset.block === "pull") {
      surround("\n\n<Pull>\n", "\n</Pull>\n\n");
    } else if (button.dataset.block === "figure") {
      // The closed set lives in SCHEMA.md §9.5 and the build enforces it. The
      // toolbar inserts the commonest query rather than offering a picker it
      // would have to keep in step with the register.
      surround('<Figure of="published" />', "");
    } else if (button.dataset.block === "image") {
      $("#body-image").click();
    }
  });
});

/* ── Images — upload on insert (UX.md §6) ─────────────────────────────────
 *
 * No separate publish-image step, deliberately unlike the producer path: a
 * post's images are part of the authored draft rather than harvested candidates
 * needing a curation decision. The server decides staged-or-published from the
 * post itself, so this does not pass a preference.
 *
 * Base64 in the JSON body, because TRD.md §2.2 does not carry
 * `python-multipart` and a transport detail is not a reason to move the
 * dependency list.
 */
function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("could not read the file"));
    reader.readAsDataURL(file);
  });
}

async function uploadImage(file) {
  const data = await readAsBase64(file);
  const response = await fetch(`/api/post/${state.slug}/image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, data }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `upload failed (${response.status})`);
  return payload;
}

$("#body-image").addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  event.target.value = "";
  if (!file || !state.slug) return;
  setSaveState(`uploading ${file.name}…`, false);
  try {
    const { url } = await uploadImage(file);
    // Plain markdown, not <TippedPhoto>. DESIGN.md §505: in-body post images
    // render at natural size with no framing, and the plate is the producer
    // page's signature rather than a component to borrow.
    const alt = window.prompt("Describe the image, for a reader who cannot see it") || "";
    surround(`\n\n![${alt}](${url})\n\n`, "");
    setSaveState("image inserted", false);
  } catch (error) {
    setSaveState(error.message, true);
    window.alert(error.message);
  }
});

$("#cover-upload").addEventListener("click", () => $("#cover-file").click());

$("#cover-file").addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  event.target.value = "";
  if (!file || !state.slug) return;
  setSaveState(`uploading ${file.name}…`, false);
  try {
    const { url } = await uploadImage(file);
    $("#f-cover").value = url;
    state.frontmatter.cover = url;
    queueSave();
    setSaveState("cover uploaded", false);
  } catch (error) {
    setSaveState(error.message, true);
    window.alert(error.message);
  }
});

function countWords() {
  // Component tags are not the author's prose, so they are not counted. Same
  // rule as `article_pipeline._word_count`.
  const prose = state.body.replace(/<Figure\b[^>]*\/>/g, " ").replace(/^#{1,6}\s.*$/gm, " ");
  const words = prose.split(/\s+/).filter(Boolean).length;
  $("#word-count").textContent = `${words} words`;
}

function countSummary() {
  const value = $("#f-summary").value;
  const max = Number($("#f-summary").getAttribute("maxlength"));
  $("#summary-count").textContent = `${value.length}/${max}`;
}

$("#f-summary").addEventListener("input", countSummary);

/* ── Sources — SCHEMA.md §9.2, at least one, and the publish gate says so ── */

function renderSources() {
  const list = $("#source-list");
  list.replaceChildren();
  const sources = state.frontmatter.sources || [];

  if (sources.length === 0) {
    list.append(
      el("li", {
        class: "hint",
        text: "No sources yet. A post cannot publish without at least one.",
      }),
    );
    return;
  }

  sources.forEach((source, index) => {
    const remove = el("button", {
      type: "button",
      class: "linkish",
      "data-remove-source": String(index),
      text: "remove",
    });
    remove.addEventListener("click", () => {
      state.frontmatter.sources.splice(index, 1);
      renderSources();
      queueSave();
    });
    list.append(
      el("li", {}, [
        el("span", { class: "source-title", text: source.title }),
        el("span", { class: "source-url mono", text: source.url }),
        remove,
      ]),
    );
  });
}

$("#source-add").addEventListener("click", () => {
  const title = $("#source-title").value.trim();
  const url = $("#source-url").value.trim();
  if (!title || !url) {
    window.alert("A source needs both a title and a URL.");
    return;
  }
  state.frontmatter.sources = state.frontmatter.sources || [];
  state.frontmatter.sources.push({ title, url });
  $("#source-title").value = "";
  $("#source-url").value = "";
  renderSources();
  queueSave();
});

/* ── The publish gate — UX.md §6, every reason named ──────────────────── */

function renderBlocks(blocks) {
  const list = $("#publish-blocks");
  list.replaceChildren();
  const publish = $("#publish");

  if (state.published) {
    publish.hidden = true;
    return;
  }

  publish.disabled = blocks.length > 0;
  for (const block of blocks) {
    list.append(el("li", { text: block }));
  }
}

/* ── The claims — UX.md §6, a deletion renders as a deletion ──────────── */

function renderClaims() {
  const section = $("#claims");
  const list = $("#claim-list");
  list.replaceChildren();

  const audit = state.factcheck;
  if (!audit || !audit.claims) {
    section.hidden = true;
    return;
  }
  section.hidden = false;

  const unresolved = audit.claims.filter((claim) => claim.verdict === "unsupported").length;
  $("#claims-count").textContent = audit.self_review
    ? `${audit.claims.length} checked by the drafting model itself`
    : `${audit.claims.length} checked, ${unresolved} unresolved`;

  for (const claim of audit.claims) {
    const row = el("li", { class: `claim claim--${claim.verdict}` });

    row.append(el("span", { class: "claim__verdict mono mono-caps", text: claim.verdict }));

    // A removed claim keeps its text struck through. A deletion that leaves no
    // trace is indistinguishable from a claim that was never made (UX.md §6).
    const text =
      claim.verdict === "removed"
        ? el("del", { class: "claim__text", text: claim.text })
        : el("span", { class: "claim__text", text: claim.text });
    row.append(text);

    row.append(el("p", { class: "claim__reason", text: claim.reason }));
    if (claim.source) {
      row.append(el("a", { class: "claim__source mono", href: claim.source, rel: "noopener", text: claim.source }));
    }

    if (claim.verdict === "unsupported" && !state.published) {
      row.append(resolveForm(claim));
    }
    list.append(row);
  }
}

/**
 * The reviewer resolving one unsupported claim.
 *
 * They cannot resolve it silently: the reason is required, and `supported`
 * requires the source that stands the claim up. The server enforces both, so a
 * caller that skipped this form still cannot rubber-stamp the audit.
 */
function resolveForm(claim) {
  const reason = el("input", { type: "text", placeholder: "Why, in one sentence" });
  const source = el("input", { type: "url", placeholder: "The source that stands it up" });

  const supported = el("button", { type: "button", class: "btn btn-quiet", text: "Supported" });
  const removed = el("button", { type: "button", class: "btn btn-quiet", text: "Removed by hand" });

  async function resolve(verdict) {
    const response = await fetch(`/api/post/${state.slug}/claim/${claim.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict, reason: reason.value, source: source.value }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      window.alert(data.detail || "Could not resolve that claim.");
      return;
    }
    await open(state.slug);
  }

  supported.addEventListener("click", () => resolve("supported"));
  removed.addEventListener("click", () => resolve("removed"));

  return el("div", { class: "claim__resolve" }, [reason, source, supported, removed]);
}

/* ── Actions ──────────────────────────────────────────────────────────── */

$("#new-post").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("#new-title").value.trim();
  if (!title) return;
  const response = await fetch("/api/post", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const data = await response.json();
  $("#new-title").value = "";
  await refreshList();
  if (data.slug) open(data.slug);
});

$("#article-chain").addEventListener("submit", async (event) => {
  event.preventDefault();
  const topic = $("#article-topic").value.trim();
  if (!topic) return;
  await fetch("/api/article/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  $("#article-topic").value = "";
  // The run streams into the log. The list is refreshed on a timer rather than
  // held open on the request, because three model calls take minutes and a
  // waiting request is the spinner UX.md §1.2 forbids.
  const poll = setInterval(refreshList, 5000);
  setTimeout(() => clearInterval(poll), 300000);
});

$("#factcheck").addEventListener("click", async () => {
  if (!state.slug) return;
  const slug = state.slug;

  // The pending debounce first, then the lock. Saving after the lock is on
  // would be refused by the server, and the author's last keystroke would be
  // the one edit the fact-check never saw.
  clearTimeout(state.saveTimer);
  await save();

  const response = await fetch(`/api/post/${slug}/factcheck`, { method: "POST" });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    window.alert(detail.detail || "Could not start the fact-check.");
    return;
  }

  setLocked(
    true,
    "The fact-check is running on this post. It rewrites the body, so editing " +
      "is held until it finishes — the editor reopens on the checked copy.",
  );

  const stop = () => {
    clearInterval(poll);
    // `open` sets the lock from the server's answer, so a run that ended
    // unlocks and one still going stays locked.
    open(slug);
  };
  const poll = setInterval(async () => {
    const data = await fetch(`/api/post/${slug}`).then((r) => r.json()).catch(() => null);
    if (!data) return;
    if (!data.factchecking) stop();
  }, 4000);
  // A stage that hangs must not leave the editor locked forever. Five minutes,
  // then reopen and take whatever the server says the state is.
  setTimeout(stop, 300000);
});

$("#publish").addEventListener("click", async () => {
  if (!state.slug) return;
  await save();
  const response = await fetch(`/api/post/${state.slug}/publish`, { method: "POST" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    window.alert(data.detail || "Could not publish.");
    await open(state.slug);
    return;
  }
  await open(state.slug);
});

$("#delete").addEventListener("click", async () => {
  if (!state.slug) return;
  if (!window.confirm("Delete this draft? There is no reject-and-keep for a post.")) return;
  const response = await fetch(`/api/post/${state.slug}`, { method: "DELETE" });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    window.alert(detail.detail || "Could not delete that draft.");
    return;
  }
  state.slug = null;
  $("#editor").hidden = true;
  $("#editor-empty").hidden = false;
  $("#preview").contentWindow.location.replace("about:blank");
  refreshList();
});

function reloadPreview() {
  if (!state.slug) return;
  $("#preview").contentWindow.location.replace(`/blog-preview/${state.slug}`);
}

/* ── Wiring ───────────────────────────────────────────────────────────── */

bindField("#f-title", "title");
bindField("#f-summary", "summary");
bindField("#f-dateline", "dateline");
bindField("#f-published", "published");
bindField("#f-cover", "cover");
bindField("#f-cover-source", "cover_source");
bindField("#f-cover-caption", "cover_caption");

startLog();
