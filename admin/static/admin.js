/*
 * admin.js — the control hub's behaviour. UX.md §1.
 *
 * Hand-written vanilla JS. No framework, no bundler, no CDN script tag
 * (TRD.md §2.1). One file, loaded once, no build step.
 *
 * The editor is built from the field contract the server sends, which comes
 * from admin/schema.py. Nothing about the contract is retyped here: a field
 * added to the contract appears in this editor without an edit to this file,
 * and a field removed from it disappears. That is the point of consumer 4 of 4
 * being one module rather than a form somebody hand-wrote in HTML.
 *
 * Copy in this file is user-facing (CLAUDE.md rule 9): Australian English, no
 * banned words, no em dashes.
 */

"use strict";

const CONFIG = JSON.parse(document.getElementById("editor-config").textContent);

const state = {
  slug: null,
  frontmatter: null,
  body: "",
  errors: {},
  ownershipBlocks: [],
  ownership: null,
  saveTimer: null,
  undoTimer: null,
  loaded: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const el = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    /* A function under an `on*` key is a real listener, not an attribute.
       Without this branch it would be stringified into the markup, where the
       closure it needs is out of scope and the handler silently does nothing. */
    else if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of [].concat(children)) {
    if (child) node.append(child);
  }
  return node;
};

/* ── The log pane — UX.md §1.2 ─────────────────────────────────────────── */

const logPane = $("#log");
const logJump = $("#log-jump");
let pinnedToBottom = true;

logPane.addEventListener("scroll", () => {
  const atBottom =
    logPane.scrollHeight - logPane.scrollTop - logPane.clientHeight < 8;
  pinnedToBottom = atBottom;
  logJump.hidden = atBottom;
});

logJump.addEventListener("click", () => {
  logPane.scrollTop = logPane.scrollHeight;
  pinnedToBottom = true;
  logJump.hidden = true;
});

function appendLog(line) {
  const empty = logPane.querySelector(".empty");
  if (empty) empty.remove();
  // Colour is never the only carrier of level: the prefix is text.
  logPane.append(
    el("li", { class: `level-${line.level}` }, [
      el("span", { class: "at", text: line.at }),
      el("span", { class: "prefix", text: line.level }),
      el("span", { text: line.message }),
    ]),
  );
  while (logPane.children.length > 500) logPane.firstElementChild.remove();
  if (pinnedToBottom) logPane.scrollTop = logPane.scrollHeight;
}

function startLogStream() {
  if (!("EventSource" in window)) {
    // Falls back to polling, per UX.md §1.2.
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

$("#log-copy").addEventListener("click", async () => {
  const text = Array.from(logPane.querySelectorAll("li"))
    .map((li) => li.textContent.replace(/\s+/g, " ").trim())
    .join("\n");
  try {
    await navigator.clipboard.writeText(text);
    $("#log-copy").textContent = "Copied";
    setTimeout(() => ($("#log-copy").textContent = "Copy log"), 1500);
  } catch (error) {
    $("#log-copy").textContent = "Copy failed, select the text by hand";
  }
});

/* ── Harvest — UX.md §1.1 ──────────────────────────────────────────────── */

async function submitHarvest(value) {
  const notes = $("#harvest-notes");
  const response = await fetch("/api/harvest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls: value }),
  }).then((r) => r.json());
  notes.hidden = response.notes.length === 0;
  notes.textContent = response.notes.join(". ");
  renderHarvestQueue(response);
  followHarvest();
}

/* The runner is serial and server-held, so the browser has to ask how it is
 * going. Polling stops as soon as nothing is queued or running, rather than
 * ticking forever against an idle queue. */
let harvestPoll = null;

function followHarvest() {
  if (harvestPoll) return;
  harvestPoll = setInterval(async () => {
    const data = await fetch("/api/harvest/queue").then((r) => r.json());
    renderHarvestQueue(data);
    const busy = (data.items || []).some(
      (item) => item.state === "QUEUED" || item.state === "RUNNING",
    );
    if (!busy) {
      clearInterval(harvestPoll);
      harvestPoll = null;
      // A block is written during the run, so the list is read after it.
      refreshBlocked();
      refreshQueue();
    }
  }, 1000);
}

$("#harvest-single").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("#harvest-url");
  if (input.value.trim()) submitHarvest(input.value.trim());
  // The input stays editable and keeps its value so a failed URL can be retried.
});

$("#harvest-batch").addEventListener("submit", (event) => {
  event.preventDefault();
  const area = $("#harvest-urls");
  if (area.value.trim()) submitHarvest(area.value);
});

function renderHarvestQueue(data) {
  $("#queue-summary").textContent = data.summary || "";
  const list = $("#harvest-queue");
  list.replaceChildren();
  if (!data.items || data.items.length === 0) {
    list.append(
      el("li", {
        class: "empty",
        text: "No URLs queued. Paste one URL, or a list of them, to begin.",
      }),
    );
    return;
  }
  data.items.forEach((item, index) => {
    const shortened =
      item.url.length > 44
        ? `${item.url.slice(0, 24)}…${item.url.slice(-16)}`
        : item.url;

    /* A STAGED row shows its slug as a link that selects the draft (UX.md
       §1.1). Getting from "that one finished" to reviewing it should not
       require finding it again in a second list. */
    let staged = null;
    if (item.state === "STAGED" && item.slug) {
      staged = el("button", {
        class: "linkish mono",
        type: "button",
        text: item.slug,
        onclick: () => {
          const row = $(`#review-queue [data-slug="${item.slug}"]`);
          if (row) selectRow(row);
        },
      });
    }

    /* UX.md §1.5 row 3. Offered ONLY on an item the server marked thin, and
       only ever by a person clicking it. Nothing escalates automatically. */
    let playwright = null;
    if (item.offer_playwright) {
      playwright = el("button", {
        class: "btn btn-quiet",
        type: "button",
        text: "Retry with Playwright",
        onclick: async (event) => {
          const button = event.currentTarget;
          button.disabled = true;
          const response = await fetch("/api/harvest/playwright", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: item.url }),
          });
          if (response.ok) {
            renderHarvestQueue(await response.json());
          } else {
            button.disabled = false;
          }
        },
      });
    }

    list.append(
      el("li", { class: "harvest-row" }, [
        el("p", { class: "mono", title: item.url }, [
          el("span", { class: `state state-${item.state.toLowerCase()}`, text: item.state }),
          el("span", { text: ` ${index + 1}. ${shortened}` }),
        ]),
        item.detail ? el("p", { class: "mono warn", text: item.detail }) : null,
        staged,
        playwright,
      ]),
    );
  });
}

$$("[data-queue-control]").forEach((button) => {
  button.addEventListener("click", async () => {
    const data = await fetch(`/api/harvest/control/${button.dataset.queueControl}`, {
      method: "POST",
    }).then((r) => r.json());
    renderHarvestQueue(data);
  });
});

/* ── The review queue — UX.md §1.3 ─────────────────────────────────────── */

function selectRow(row) {
  if (!row) return;
  $$(".draft-row").forEach((other) => other.setAttribute("aria-selected", "false"));
  row.setAttribute("aria-selected", "true");
  row.scrollIntoView({ block: "nearest" });
  loadDraft(row.dataset.slug);
}

function bindRows() {
  $$(".draft-row").forEach((row) => {
    row.addEventListener("click", () => selectRow(row));
  });
}

function moveSelection(step) {
  const rows = $$(".draft-row");
  if (rows.length === 0) return;
  const current = rows.findIndex((row) => row.getAttribute("aria-selected") === "true");
  const next = current === -1 ? 0 : Math.min(Math.max(current + step, 0), rows.length - 1);
  selectRow(rows[next]);
}

async function refreshQueue(rows, counts) {
  if (!rows) {
    const data = await fetch("/api/queue").then((r) => r.json());
    rows = data.rows;
    counts = data.counts;
  }
  $("#queue-counts").textContent = counts || "";
  const list = $("#review-queue");
  list.replaceChildren();
  if (rows.length === 0) {
    list.append(
      el("li", {
        class: "empty",
        text: "No drafts staged. Harvest a producer URL to begin.",
      }),
    );
    return;
  }
  for (const row of rows) {
    const item = el(
      "li",
      {
        class: "draft-row",
        role: "option",
        "aria-selected": row.slug === state.slug ? "true" : "false",
        "data-slug": row.slug,
        tabindex: "-1",
      },
      [
        el("p", { class: "draft-name", text: row.name }),
        el("p", {
          class: "draft-meta mono",
          text: [row.slug, row.where, row.category].filter(Boolean).join(" · "),
        }),
        el("p", { class: "chips" }, [
          el("span", {
            class: `chip chip-${row.status.toLowerCase().replace(/ /g, "-")}`,
            text: row.status,
          }),
          el("span", {
            class: `chip chip-${row.ownership.toLowerCase().replace(/ /g, "-")}`,
            text: row.ownership,
          }),
          el("span", {
            class: `age mono${row.stale ? " warn" : ""}`,
            text: row.age + (row.stale ? " stale" : ""),
          }),
        ]),
        row.detail ? el("p", { class: "draft-detail mono", text: row.detail }) : null,
      ],
    );
    list.append(item);
  }
  bindRows();
}

/* ── The deploy strip — UX.md §1.6 ─────────────────────────────────────────
 *
 * The only path from disk to live. Every write in this system stops at
 * "updated on disk" and waits for a human to click Deploy (TRD.md §2.4), so
 * this is the one control in the hub that reaches the internet.
 *
 * Nothing is committed until the diff has been rendered. The dialog is not a
 * confirmation prompt: it is the file list, with the change type per file, and
 * it is where a path nobody meant to publish becomes visible.
 */

async function refreshDeployStatus() {
  const status = await fetch("/api/deploy").then((r) => r.json());
  $("#deploy-status").textContent = status.summary;
  // A deploy in flight disables the button rather than hiding it, so the
  // control does not move under the pointer mid-run.
  $("#deploy-open").disabled = status.file_count === 0 || status.running;
  return status;
}

/* A run streams into the log pane, so the browser only has to ask when it has
 * finished, to repaint the summary. Polling stops the moment it has. */
let deployPoll = null;

function followDeploy() {
  if (deployPoll) return;
  deployPoll = setInterval(async () => {
    const status = await refreshDeployStatus();
    if (!status.running) {
      clearInterval(deployPoll);
      deployPoll = null;
    }
  }, 2000);
}

function renderDeployPreview(preview) {
  const refusal = $("#deploy-refusal");
  const refusals = [];
  if (preview.guard_violations.length) {
    refusals.push(
      "Refused. These files are tracked under a gitignored path, so they would " +
        "be committed: " +
        preview.guard_violations.join(", ") +
        ". Untrack them with git rm --cached, then try again.",
    );
  }
  if (preview.unexpected.length) {
    refusals.push(
      "Refused. These changed files sit outside the publish set: " +
        preview.unexpected.join(", ") +
        ". Commit or revert them by hand first. The deploy strip publishes " +
        "content, never source.",
    );
  }
  refusal.hidden = refusals.length === 0;
  refusal.textContent = refusals.join(" ");

  const count = preview.files.length;
  $("#deploy-count").textContent = count
    ? `${count} file${count !== 1 ? "s" : ""} to commit and push.`
    : "Nothing to publish. Approve a draft first.";

  const list = $("#deploy-files");
  list.replaceChildren();
  for (const item of preview.files) {
    list.append(
      el("li", {}, [
        el("span", { class: "change", text: item.change }),
        el("span", { text: item.path }),
      ]),
    );
  }

  $("#deploy-message").value = preview.commit_message;
  $("#deploy-run").disabled = preview.blocked || count === 0;
}

$("#deploy-open").addEventListener("click", async () => {
  const preview = await fetch("/api/deploy/preview").then((r) => r.json());
  renderDeployPreview(preview);
  $("#deploy-dialog").showModal();
});

$("#deploy-run").addEventListener("click", async () => {
  const response = await fetch("/api/deploy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: $("#deploy-message").value }),
  });
  if (!response.ok) {
    const problem = await response.json();
    $("#deploy-refusal").hidden = false;
    $("#deploy-refusal").textContent = problem.detail;
    return;
  }
  // Closed straight away: the run reports into the log pane, which is the one
  // place pipeline output goes (UX.md §1.2), and a dialog over it would hide
  // the thing the reader needs to watch.
  $("#deploy-dialog").close();
  $("#deploy-open").disabled = true;
  followDeploy();
});

/* ── The review pane — UX.md §1.4 ──────────────────────────────────────── */

async function loadDraft(slug) {
  const data = await fetch(`/api/draft/${slug}`).then((r) => r.json());
  state.slug = slug;
  state.loaded = false;
  $("#review-empty").hidden = true;
  $("#review-body").hidden = false;
  $("#reject-panel").hidden = true;
  // The undo offer deliberately survives this. Approve advances selection to
  // the next queue item (UX.md §1.4 step 7), and hiding undo here would take
  // the offer away in the same tick it was made. Its own timer hides it.

  if (data.unreadable) {
    // UX.md §1.3: an unreadable file never crashes or empties the queue.
    $("#editor-groups").replaceChildren(
      el("p", {
        class: "field-error",
        text: `This file could not be parsed: ${data.unreadable}`,
      }),
      el("p", {
        class: "note",
        text: "Open it in an editor and fix the frontmatter, or reject it.",
      }),
    );
    $("#preview").src = `/preview/${slug}`;
    return;
  }

  state.frontmatter = data.frontmatter;
  state.body = data.body;
  state.errors = data.errors;
  state.ownershipBlocks = data.ownership_blocks;
  renderEditor(data);
  $("#preview").src = `/preview/${slug}`;
  state.loaded = true;
  loadImages(slug);
}

/* ── Candidate images — UX.md §4 ───────────────────────────────────────── */

let selectedImage = null;

const hostOf = (url) => {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
};

const fileOf = (url) => {
  try {
    return decodeURIComponent(new URL(url).pathname.split("/").pop() || url);
  } catch {
    return url;
  }
};

async function loadImages(slug) {
  selectedImage = null;
  const pane = $("#images-pane");
  const strip = $("#image-strip");
  const publish = $("#image-publish");
  const remove = $("#remove-image");
  pane.hidden = false;
  strip.replaceChildren();
  publish.hidden = true;

  const data = await fetch(`/api/draft/${slug}/images`).then((r) => r.json());

  /* An already-published image offers only its reverse. UX.md §4 step 4 makes
     Remove one action, on a staged draft or a published producer alike, because
     a takedown request is not the moment to be assembling a procedure. */
  remove.hidden = !data.published;

  const images = data.images || [];
  $("#images-empty").hidden = images.length > 0;
  if (images.length === 0) return;

  images.forEach((image) => {
    const thumb = el("li", { class: "image-candidate" }, [
      el("img", {
        src: `/api/draft/${slug}/images/${image.file}`,
        alt: "",
        loading: "lazy",
      }),
      el("p", { class: "mono faded", text: `${image.width}×${image.height}` }),
      /* The source is VISIBLE TEXT, not a tooltip. This is the only step where
         a reviewer can tell a producer's own photograph from a stock library's
         or another label's, and a tooltip is not a place people look.

         The HOST is on its own line and carries the weight, because the host is
         the thing being judged. Printing the whole URL as one run wrapped these
         to six lines each and buried the only part that answers the question.
         The full value stays in `title` and is one hover away. */
      el("p", { class: "mono image-host", text: hostOf(image.source_url) }),
      el("p", {
        class: "mono image-source",
        text: fileOf(image.source_url),
        title: image.source_url,
      }),
    ]);
    thumb.addEventListener("click", () => {
      selectedImage = image.file;
      $$(".image-candidate").forEach((node) =>
        node.classList.toggle("is-selected", node === thumb),
      );
      publish.hidden = false;
      if (!$("#image-caption").value) {
        $("#image-caption").value = data.suggested_caption || "";
      }
    });
    strip.append(thumb);
  });
}

$("#publish-image").addEventListener("click", async () => {
  if (!selectedImage || !state.slug) return;
  const response = await fetch(`/api/draft/${state.slug}/image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file: selectedImage,
      caption: $("#image-caption").value,
      alt: $("#image-alt").value,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    $("#action-reason").textContent = error.detail || "Could not publish the image.";
    return;
  }
  await loadDraft(state.slug);
});

$("#remove-image").addEventListener("click", async () => {
  if (!state.slug) return;
  await fetch(`/api/draft/${state.slug}/image`, { method: "DELETE" });
  await loadDraft(state.slug);
});

function setValue(path, value) {
  // `path` is `field` or `field.subfield`. Frontmatter has one level of nesting.
  const [field, sub] = path.split(".");
  if (sub === undefined) {
    if (value === undefined) delete state.frontmatter[field];
    else state.frontmatter[field] = value;
  } else {
    if (!state.frontmatter[field] || typeof state.frontmatter[field] !== "object") {
      state.frontmatter[field] = {};
    }
    state.frontmatter[field][sub] = value;
  }
  queueSave();
}

function getValue(path) {
  const [field, sub] = path.split(".");
  const value = state.frontmatter[field];
  if (sub === undefined) return value;
  return value && typeof value === "object" ? value[sub] : undefined;
}

function fieldShell(name, spec, control, extra) {
  const wrapper = el("div", { class: "field", "data-field": name }, [
    el("label", { class: "field-label", for: `f-${name}`, text: spec.label }),
    control,
  ]);
  if (spec.help) wrapper.append(el("p", { class: "field-help", text: spec.help }));
  if (extra) wrapper.append(extra);
  const message = state.errors[name];
  if (message) {
    wrapper.classList.add("field-invalid");
    wrapper.append(el("p", { class: "field-error", text: message }));
  }
  return wrapper;
}

function textInput(name, path, type, value, onInput) {
  const input = el("input", {
    type,
    id: `f-${name}`,
    value: value === null || value === undefined ? "" : String(value),
  });
  input.addEventListener("input", () => {
    const raw = input.value.trim();
    if (type === "number") {
      setValue(path, raw === "" ? null : Number(raw));
    } else {
      setValue(path, raw === "" ? null : input.value);
    }
    if (onInput) onInput(input.value);
  });
  return input;
}

function selectInput(name, path, options, value, onChange) {
  const select = el("select", { id: `f-${name}` });
  for (const option of options) {
    const node = el("option", { value: option.value, text: option.label });
    if (option.value === value) node.selected = true;
    select.append(node);
  }
  select.addEventListener("change", () => {
    setValue(path, select.value);
    if (onChange) onChange(select.value);
  });
  return select;
}

function multiselect(name, options, selected, onChange) {
  const chosen = new Set(selected || []);
  const box = el("div", { class: "multiselect", id: `f-${name}` });
  for (const option of options) {
    const button = el("button", {
      type: "button",
      class: "toggle",
      "aria-pressed": chosen.has(option.value) ? "true" : "false",
      text: option.label,
    });
    button.addEventListener("click", () => {
      if (chosen.has(option.value)) chosen.delete(option.value);
      else chosen.add(option.value);
      button.setAttribute("aria-pressed", chosen.has(option.value) ? "true" : "false");
      onChange(options.filter((o) => chosen.has(o.value)).map((o) => o.value));
    });
    box.append(button);
  }
  return box;
}

function toggles(name, keys, values, onChange) {
  const current = { ...(values || {}) };
  const box = el("div", { class: "toggles", id: `f-${name}` });
  for (const key of keys) {
    const button = el("button", {
      type: "button",
      class: "toggle",
      "aria-pressed": current[key.value] === true ? "true" : "false",
      text: key.label.toLowerCase(),
    });
    button.addEventListener("click", () => {
      current[key.value] = current[key.value] !== true;
      button.setAttribute("aria-pressed", current[key.value] ? "true" : "false");
      onChange({ ...current });
    });
    box.append(button);
  }
  return box;
}

function readonlyBlock(value) {
  return el("pre", {
    class: "readonly-block",
    text: value === undefined || value === null ? "not recorded" : JSON.stringify(value, null, 2),
  });
}

/* ── The independence panel — UX.md §1.4.1 to §1.4.3 ───────────────────────
 *
 * "It is the one part of the hub where the interface's job is to make a
 * reviewer slow down."
 *
 * The panel is the first thing in the review pane, above the producer's name.
 * It cannot be collapsed and it renders for every draft including a clear one.
 *
 * THE VERDICT IS DISPLAYED, NEVER EDITED. There is no control here that sets
 * it, and there is none anywhere else in this hub either (UX.md §1.4.5 rule 4,
 * CLAUDE.md rule 8 in interface form). What a reviewer records is evidence and
 * resolutions; the gate is then satisfied or it is not.
 */

const VERDICT_WORD = { clear: "Clear", check: "Check", reject: "Reject" };

function resolutionControls(key, current, note, options) {
  const select = el("select", { class: "resolution", "data-signal": key }, [
    el("option", { value: "", text: "Unresolved" }),
  ]);
  for (const option of options) {
    select.append(
      el("option", {
        value: option.value,
        text: option.label + (option.note_required ? " (note required)" : ""),
        selected: current === option.value,
      }),
    );
  }
  const field = el("input", {
    type: "text",
    class: "resolution-note",
    "data-signal": key,
    value: note || "",
    placeholder: "One line: why this is resolved",
  });
  select.addEventListener("change", saveOwnership);
  field.addEventListener("change", saveOwnership);
  return el("div", { class: "resolution-controls" }, [select, field]);
}

function denyListRow(row, labels, panel) {
  const cells = [
    el("td", { class: "mono", text: labels[row.check] || row.check }),
    el("td", { class: "mono", text: row.value || "not on the page" }),
    el("td", { class: `mono deny-${row.state.replace(/ /g, "-")}`, text: row.state }),
  ];
  const line = el("tr", {}, cells);
  if (!row.match) return [line];

  // On a hit the row expands to the matched record in full. The panel never
  // says only "matched": a reviewer must be able to see the evidence behind a
  // block without opening a JSON file (UX.md §1.4.2).
  const m = row.match;
  const detail = el("td", { colspan: "3" }, [
    el("p", { class: "deny-parent", text: m.parent }),
    el("p", {
      class: "note",
      text:
        `Matched ${JSON.stringify(m.matched)} in ${m.matched_in}` +
        `${m.exact ? "" : ", as part of a longer name"}. ` +
        `Category ${m.category || "not recorded"}. ` +
        `Record verdict ${m.record_verdict}${
          m.verdict === m.record_verdict ? "" : `, applied as ${m.verdict}`
        }.`,
    }),
  ]);
  if (m.abn_evidence) {
    const e = m.abn_evidence;
    detail.append(
      el("p", {
        class: "note mono",
        text: `ABN ${e.abn}, ${e.entity || "entity not recorded"}, verified ${e.verified || "undated"}.`,
      }),
    );
    if (e.quote) detail.append(el("p", { class: "note quote", text: `"${e.quote}"` }));
  }
  if (m.source) {
    detail.append(
      el("p", { class: "note" }, [
        el("a", { href: m.source, rel: "noopener", target: "_blank", text: m.source }),
        el("span", { class: "faded", text: ` · updated ${m.updated || "undated"}` }),
      ]),
    );
  }
  if (m.note) detail.append(el("p", { class: "note faded", text: m.note }));

  // A `check` hit carries the same resolution control the signal rows use. A
  // named deny-list record is the strongest evidence on this screen, and a
  // reviewer has to say what they make of it before the draft can be approved.
  // A `reject` hit gets no control: there is no resolution for a reject, and
  // offering one would be the override UX.md §1.4.4 forbids.
  const pending = (panel && panel.hits_to_resolve) || [];
  const hit = pending.find((entry) => entry.check === row.check);
  if (hit && panel.resolutions.length) {
    detail.append(
      el("p", {
        class: "note",
        text: `Resolve this match before approving. ${
          m.verdict === "check" ? "The record's verdict is check, not reject." : ""
        }`,
      }),
      resolutionControls(hit.key, hit.resolution, hit.note, panel.resolutions),
    );
  }
  return [line, el("tr", { class: "deny-detail" }, [detail])];
}

function signalRow(row, panel) {
  const label = panel.signal_labels[row.key] || row.key;
  const cell = el("td", {});

  if (!row.populated) {
    cell.append(el("p", { class: "faded", text: "nothing extracted" }));
    return el("tr", {}, [el("td", { class: "mono", text: label }), cell]);
  }

  const formatted = panel.abn_display[row.key];
  row.items.forEach((item, index) => {
    if (formatted) {
      cell.append(
        el("p", { class: "mono" }, [
          document.createTextNode(formatted.formatted[index] || item),
          el("span", { text: " " }),
          el("a", {
            href: formatted.lookup[index],
            rel: "noopener",
            target: "_blank",
            text: "ABR lookup",
          }),
        ]),
      );
    } else {
      cell.append(el("p", { class: "quote", text: `"${item}"` }));
    }
  });

  // UX.md §1.4.3: every populated row carries a resolution control and a
  // one-line note. While any escalating row is unresolved, Approve is disabled
  // and the reason is stated in text beside the button, not only as a tooltip.
  //
  // Amended 2026-08-07: a populated row that does not escalate says so. Without
  // this the reviewer sees a resolution control on a row that never blocks and
  // has no way to tell it apart from one that does.
  const escalates = (panel.escalating_keys || []).includes(row.key);
  if (!escalates) {
    cell.append(
      el("p", {
        class: "note faded",
        text:
          "Recorded as evidence. This statement names no parent, so it does " +
          "not hold the entry. Resolve it if you want the reasoning kept.",
      }),
    );
  } else if (row.key === "statements") {
    cell.append(
      el("p", {
        class: "note warn",
        text: "This statement places the business inside a group. Resolve it before approving.",
      }),
    );
  }
  cell.append(resolutionControls(row.key, row.resolution, row.note, panel.resolutions));

  return el("tr", {}, [el("td", { class: "mono", text: label }), cell]);
}

function renderOwnershipPanel(data) {
  const panel = data.ownership;
  const section = el("section", { class: "ownership-panel", id: "ownership-panel" });

  if (!panel) {
    // Not a clear panel, and not an empty one either. A draft nothing has
    // looked at is its own state, and it blocks approval.
    section.append(
      el("p", { class: "ownership-verdict" }, [
        el("span", { class: "chip chip-not-determined", text: "NOT DETERMINED" }),
      ]),
      el("p", {
        class: "note warn",
        text:
          "No ownership determination exists for this draft. Nothing has checked " +
          "the deny-list or read the ownership signals, so there is nothing to " +
          "display and this draft cannot be approved.",
      }),
    );
    return section;
  }

  const verdict = String(panel.verdict || "").toLowerCase();
  section.append(
    el("p", { class: "ownership-verdict" }, [
      el("span", { class: `chip chip-${panel.chip.toLowerCase().replace(/ /g, "-")}`, text: panel.chip }),
      el("strong", { class: "verdict-word", text: VERDICT_WORD[verdict] || "Not determined" }),
    ]),
    el("p", { class: "ownership-basis", text: panel.basis || "" }),
  );

  if (panel.verdict_overridden_from) {
    section.append(
      el("p", {
        class: "note warn prominent",
        text:
          "This draft was re-harvested after an automatic ownership reject. " +
          "Read the signals carefully.",
      }),
    );
  }

  // The three named checks, always all three, whether they hit or not.
  const body = el("tbody");
  for (const row of panel.deny_list.rows) {
    for (const node of denyListRow(row, panel.check_labels, panel)) body.append(node);
  }
  section.append(
    el("div", { class: "deny-block" }, [
      el("p", {
        class: "mono mono-caps",
        text: `Deny-list, data/ownership.json (updated ${panel.deny_list.updated || "undated"})`,
      }),
      el("table", { class: "deny-table" }, [body]),
    ]),
  );

  // The signals table, always rendered. The empty case is shown as words rather
  // than as an absent row, because the absence of signals is itself a finding
  // and it is explicitly NOT evidence of independence (UX.md §1.4.5).
  const signalBody = el("tbody");
  for (const row of panel.signals) signalBody.append(signalRow(row, panel));
  const signalBlock = el("div", { class: "signal-block" }, [
    el("p", { class: "mono mono-caps", text: "Ownership signals" }),
  ]);
  if (panel.populated === 0) {
    signalBlock.append(
      el("p", { class: "note", text: "No ownership signals extracted from this page." }),
      el("p", {
        class: "note faded",
        text:
          "That is not evidence of independence. A corporate portfolio site " +
          "naming no parent is the normal case, not the exception.",
      }),
    );
  }
  signalBlock.append(el("table", { class: "signal-table" }, [signalBody]));
  section.append(signalBlock);

  // Conflict handling. Where sources conflict the registry wins, and the note
  // is written to the sidecar's confidence_notes and surfaced on every later
  // visit to this draft. It is not published frontmatter (UX.md §1.4.2).
  const existing = (panel.confidence_notes || [])
    .filter((line) => String(line).startsWith("Conflict noted:"))
    .map((line) => String(line).slice("Conflict noted:".length).trim())[0];
  const conflict = el("input", {
    type: "text",
    id: "conflict-note",
    value: existing || "",
    placeholder: "Where sources disagree, the registry wins. Note the conflict here.",
  });
  conflict.addEventListener("change", saveOwnership);
  section.append(
    el("div", { class: "field", "data-field": "_conflict" }, [
      el("label", { for: "conflict-note", text: "Conflict noted" }),
      conflict,
    ]),
  );

  for (const line of panel.confidence_notes || []) {
    if (!String(line).startsWith("Conflict noted:")) {
      section.append(el("p", { class: "note faded", text: line }));
    }
  }

  // Dates side by side, so a reviewer can see how old the ownership evidence is
  // relative to the rest of the entry. Display only, no block.
  const source = (data.frontmatter && data.frontmatter.ownership_source) || {};
  section.append(
    el("p", { class: "note mono faded" }, [
      el("span", { text: `ownership_source.date ${source.date || "not recorded"}` }),
      el("span", { text: "   " }),
      el("span", { text: `verified ${(data.frontmatter || {}).verified || "not recorded"}` }),
    ]),
  );

  // A non-null parent_company blocks approval unconditionally, and the panel
  // offers the reject with the parent's name pre-filled (UX.md §1.4.2).
  const parent = (data.frontmatter || {}).parent_company;
  if (parent) {
    const reject = el("button", {
      type: "button",
      class: "btn btn-danger",
      text: "Reject as corporately owned",
    });
    reject.addEventListener("click", () => {
      $("#reject-panel").hidden = false;
      $("#reject-reason").value = `Not an independent producer. Owned by ${parent}.`;
      $("#reject-reason").focus();
    });
    section.append(
      el("p", {
        class: "note warn prominent",
        text:
          "parent_company is set. This producer cannot be published " +
          "(SCHEMA.md §4.1). Reject it, or clear the field if it was entered in error.",
      }),
      reject,
    );
  }

  return section;
}

async function saveOwnership() {
  if (!state.slug) return;
  const resolutions = {};
  $$(".resolution").forEach((select) => {
    const key = select.dataset.signal;
    const note = $(`.resolution-note[data-signal="${key}"]`);
    resolutions[key] = { resolution: select.value, note: note ? note.value : "" };
  });
  const conflictNode = $("#conflict-note");
  const response = await fetch(`/api/draft/${state.slug}/ownership`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resolutions,
      conflict_note: conflictNode ? conflictNode.value : "",
    }),
  });
  if (!response.ok) {
    $("#save-state").textContent = "ownership save failed";
    return;
  }
  const result = await response.json();
  state.ownership = result.ownership;
  state.ownershipBlocks = result.ownership_blocks || [];
  $("#save-state").textContent = `saved ${result.saved}`;
  // Repaint the chip in the queue row without a full reload: resolving the last
  // signal moves it from CHECK to RESOLVED and that has to be visible at once.
  const row = $(`.draft-row[data-slug="${state.slug}"]`);
  if (row) {
    const chip = row.querySelector(".chip + .chip");
    if (chip) {
      chip.textContent = result.ownership_chip;
      chip.className = `chip chip-${result.ownership_chip.toLowerCase().replace(/ /g, "-")}`;
    }
  }
  renderActions();
}

function renderEditor(data) {
  const container = $("#editor-groups");
  container.replaceChildren();

  state.ownership = data.ownership || null;
  container.append(renderOwnershipPanel(data));

  if (data.duplicate) {
    container.append(
      el("p", {
        class: "duplicate-warning",
        text:
          `This looks like ${data.duplicate.name} (${data.duplicate.slug}), already ` +
          `${data.duplicate.where}. This is a warning, and the decision is yours.`,
      }),
    );
  }

  for (const group of CONFIG.groups) {
    // CONFIG.fields is a list in SCHEMA.md §2's field order, not an object.
    // Jinja's tojson sorts object keys, which would alphabetise the editor.
    const fields = CONFIG.fields.filter((spec) => spec.group === group.key);
    if (fields.length === 0) continue;

    // The ownership group is first, pinned, and cannot be collapsed (UX.md §1.4).
    const pinned = group.key === "ownership";
    const box = pinned
      ? el("section", { class: "group-pinned", id: "group-ownership" }, [
          el("p", { class: "pinned-title", text: group.title }),
        ])
      : el("details", { class: "group", open: group.key !== "provenance" }, [
          el("summary", { text: group.title }),
        ]);

    for (const spec of fields) {
      const control = buildField(spec.name, spec, data);
      if (control) box.append(control);
    }

    if (pinned) {
      box.append(
        el("p", {
          class: "field-help",
          text:
            "A source that fails to mention a parent is not evidence of absence. " +
            "It must positively state who owns the business.",
        }),
        el("p", {
          class: "field-help",
          text:
            "Any one of the three kinds of evidence is sufficient: a registry " +
            "lookup, the producer's own published ownership statement, or a " +
            "named independent trade source.",
        }),
      );
    }
    container.append(box);
  }

  // An unknown key belongs to no field, so it has no field to highlight. It is
  // painted at the top of the editor, on first render as well as after a save.
  paintErrors();
  renderActions();
}

function buildField(name, spec, data) {
  const value = getValue(name);

  switch (spec.widget) {
    case "text":
    case "url":
      return fieldShell(
        name,
        spec,
        textInput(name, name, spec.widget === "url" ? "url" : "text", value),
      );

    case "nullable_text": {
      // UX.md §1.4.2: null renders as the literal word null, never as an empty
      // box. An empty box reads as "not filled in yet", and null here is a
      // positive assertion.
      const input = el("input", {
        type: "text",
        id: `f-${name}`,
        value: value === null || value === undefined ? "null" : String(value),
      });
      input.addEventListener("input", () => {
        const raw = input.value.trim();
        setValue(name, raw === "" || raw === "null" ? null : input.value);
      });
      return fieldShell(name, spec, input);
    }

    case "number":
      return fieldShell(
        name,
        spec,
        textInput(name, name, "number", value),
        name === "annual_production_cases" && data.implied_band
          ? el("p", {
              class: "counter",
              text: `That figure implies the ${data.implied_band.replace(/_/g, " ")} band.`,
            })
          : null,
      );

    case "boolean": {
      const button = el("button", {
        type: "button",
        class: "toggle",
        "aria-pressed": value === true ? "true" : "false",
        id: `f-${name}`,
        text: spec.label.toLowerCase(),
      });
      button.addEventListener("click", () => {
        const next = button.getAttribute("aria-pressed") !== "true";
        button.setAttribute("aria-pressed", next ? "true" : "false");
        setValue(name, next);
      });
      return fieldShell(name, spec, button);
    }

    case "summary": {
      const area = el("textarea", { id: `f-${name}`, rows: "3" });
      area.value = value === null || value === undefined ? "" : String(value);
      const counter = el("span", { class: "counter" });
      const paint = () => {
        counter.textContent = `${area.value.length} of ${CONFIG.summaryMax} characters`;
        counter.classList.toggle("over", area.value.length > CONFIG.summaryMax);
      };
      paint();
      area.addEventListener("input", () => {
        setValue(name, area.value);
        paint();
      });
      return fieldShell(name, spec, area, counter);
    }

    case "select":
      return fieldShell(
        name,
        spec,
        selectInput(
          name,
          name,
          CONFIG.options[selectOptionKey(name)],
          value,
          name === "cellar_door" ? () => rerender() : null,
        ),
      );

    case "certification":
      return fieldShell(
        name,
        spec,
        selectInput(name, name, CONFIG.options.certification, value, (next) => {
          // SCHEMA.md §2a rules 2 and 3, live and in both directions.
          if (next !== "certified") setValue(`${name}_certifier`, null);
          rerender();
        }),
      );

    case "certifier": {
      const subject = name.replace("_certifier", "");
      const enabled = getValue(subject) === "certified";
      const input = textInput(name, name, "text", value);
      if (!enabled) {
        input.disabled = true;
        input.value = "";
      }
      return fieldShell(
        name,
        spec,
        input,
        el("p", {
          class: "field-help",
          text: enabled
            ? "Name the certifier. ACO, NASAA, AUS-QUAL, Demeter."
            : `Available once ${subject} is certified.`,
        }),
      );
    }

    case "location": {
      const box = el("div", { id: `f-${name}` });
      const location = value || {};
      for (const part of ["address", "suburb"]) {
        box.append(
          el("div", { class: "field" }, [
            el("label", { class: "field-label", for: `f-location-${part}`, text: part }),
            (() => {
              const input = el("input", {
                type: "text",
                id: `f-location-${part}`,
                value: location[part] || "",
              });
              input.addEventListener("input", () => {
                setValue(`location.${part}`, input.value.trim() || undefined);
              });
              return input;
            })(),
          ]),
        );
      }
      box.append(
        el("div", { class: "field" }, [
          el("label", { class: "field-label", for: "f-location-state", text: "state" }),
          selectInput("location-state", "location.state", CONFIG.options.state, location.state),
        ]),
      );
      // No coordinate inputs. Coordinates are geocoded and cached (UX.md §1.4).
      const hasCoordinates =
        typeof location.latitude === "number" && typeof location.longitude === "number";
      box.append(
        el("p", {
          class: "field-help",
          text: hasCoordinates
            ? `Coordinates ${location.latitude}, ${location.longitude}. Geocoded, and read-only here.`
            : "no coordinates, this producer publishes without a map pin",
        }),
      );
      // A miss is silent by design — null coordinates never block a publish —
      // so the only way to notice a geocoder that is refusing requests is to
      // look at this line. Offer the repair right here, where it is noticed.
      if (!hasCoordinates && (location.address || location.suburb)) {
        const button = el("button", {
          type: "button",
          class: "btn btn-quiet",
          text: "Look up coordinates",
        });
        const outcome = el("p", { class: "field-help" });
        button.addEventListener("click", async () => {
          button.disabled = true;
          button.textContent = "Looking up…";
          outcome.textContent = "";
          try {
            const response = await fetch(`/api/draft/${state.slug}/geocode`, {
              method: "POST",
            });
            const result = await response.json();
            if (result.blocked || result.found === false) {
              outcome.className = "field-help warn";
              outcome.textContent = result.blocked || result.detail;
              button.disabled = false;
              button.textContent = "Look up coordinates";
            } else {
              outcome.className = "field-help";
              outcome.textContent = `Found ${result.latitude}, ${result.longitude}.`;
              await loadDraft(state.slug);
            }
          } catch (error) {
            outcome.className = "field-help warn";
            outcome.textContent = `Lookup failed: ${error.message}`;
            button.disabled = false;
            button.textContent = "Look up coordinates";
          }
        });
        box.append(button, outcome);
      }
      return fieldShell(name, spec, box);
    }

    case "region_multiselect":
      return fieldShell(
        name,
        spec,
        multiselect(name, CONFIG.options.regions, value, (next) => {
          setValue(name, next);
          rerender();
        }),
      );

    case "primary_region_select": {
      // Constrained to the current members of `regions`; changing `regions`
      // re-validates it immediately (UX.md §1.4, SCHEMA.md §2a rule 4).
      const members = getValue("regions") || [];
      const options = CONFIG.options.regions.filter((option) =>
        members.includes(option.value),
      );
      if (options.length === 0) {
        return fieldShell(
          name,
          spec,
          el("p", { class: "field-help", text: "Choose at least one region first." }),
        );
      }
      return fieldShell(name, spec, selectInput(name, name, options, value));
    }

    case "subregion_multiselect": {
      // Constrained to the subregions of the selected regions (§2a rule 5).
      const members = getValue("regions") || [];
      const options = CONFIG.options.subregions.filter((option) =>
        members.includes(option.region),
      );
      if (options.length === 0) {
        return fieldShell(
          name,
          spec,
          el("p", {
            class: "field-help",
            text: "The selected regions have no registered subregions.",
          }),
        );
      }
      return fieldShell(
        name,
        spec,
        multiselect(name, options, value, (next) =>
          setValue(name, next.length ? next : undefined),
        ),
      );
    }

    case "multiselect":
      return fieldShell(
        name,
        spec,
        multiselect(name, CONFIG.options[selectOptionKey(name)], value, (next) =>
          setValue(name, next.length ? next : undefined),
        ),
      );

    case "toggles":
      return fieldShell(
        name,
        spec,
        // All four practice keys always rendered, always written. There is no
        // way to add a fifth (UX.md §1.4).
        toggles(name, CONFIG.practiceKeys, value, (next) => {
          const complete = {};
          for (const key of CONFIG.practiceKeys) complete[key.value] = next[key.value] === true;
          setValue(name, complete);
        }),
      );

    case "toggles_optional": {
      const clear = el("button", { type: "button", class: "linkish", text: "Clear logistics" });
      clear.addEventListener("click", () => {
        // Removes the object rather than writing ten false values (UX.md §1.4).
        setValue(name, undefined);
        rerender();
      });
      return fieldShell(
        name,
        spec,
        toggles(name, CONFIG.logisticsKeys, value, (next) => {
          const kept = {};
          for (const key of CONFIG.logisticsKeys) {
            if (next[key.value] === true) kept[key.value] = true;
          }
          setValue(name, Object.keys(kept).length ? kept : undefined);
        }),
        clear,
      );
    }

    case "tasting_fee": {
      const fee = value || {};
      const box = el("div", { id: `f-${name}` });
      const amount = el("input", {
        type: "number",
        id: "f-tasting-fee",
        value: fee.fee_aud === null || fee.fee_aud === undefined ? "" : String(fee.fee_aud),
      });
      amount.addEventListener("input", () => {
        setValue("tasting_fee.fee_aud", amount.value === "" ? null : Number(amount.value));
      });
      box.append(
        el("div", { class: "field" }, [
          el("label", { class: "field-label", for: "f-tasting-fee", text: "fee in dollars" }),
          amount,
        ]),
      );

      const waived = el("button", {
        type: "button",
        class: "toggle",
        "aria-pressed": fee.waived_on_purchase === true ? "true" : "false",
        text: "waived on purchase",
      });
      waived.addEventListener("click", () => {
        const next = waived.getAttribute("aria-pressed") !== "true";
        waived.setAttribute("aria-pressed", next ? "true" : "false");
        setValue("tasting_fee.waived_on_purchase", next);
      });
      box.append(el("div", { class: "toggles" }, [waived]));

      // SCHEMA.md §2a rule 8: the amounts are scraped in Python and displayed
      // here, so the reviewer sees the corroboration or its absence.
      box.append(
        el("p", {
          class: "counter",
          text:
            data.cost_amounts && data.cost_amounts.length
              ? `The cost line states ${data.cost_amounts.map((n) => `$${n}`).join(", ")}.`
              : "The cost line states no dollar amount.",
        }),
      );

      const remove = el("button", { type: "button", class: "linkish", text: "Delete tasting fee" });
      remove.addEventListener("click", () => {
        setValue(name, undefined);
        rerender();
      });
      box.append(remove);
      return fieldShell(name, spec, box);
    }

    case "faq": {
      const pairs = Array.isArray(value) ? value.slice() : [];
      const box = el("div", { id: `f-${name}` });
      pairs.forEach((pair, index) => {
        const question = el("input", { type: "text", value: pair.question || "" });
        const answer = el("textarea", { rows: "2" });
        answer.value = pair.answer || "";
        question.addEventListener("input", () => {
          pairs[index] = { ...pairs[index], question: question.value };
          setValue(name, pairs);
        });
        answer.addEventListener("input", () => {
          pairs[index] = { ...pairs[index], answer: answer.value };
          setValue(name, pairs);
        });
        const remove = el("button", { type: "button", class: "linkish", text: "Remove" });
        remove.addEventListener("click", () => {
          pairs.splice(index, 1);
          setValue(name, pairs.length ? pairs : undefined);
          rerender();
        });
        box.append(el("div", { class: "field" }, [question, answer, remove]));
      });
      if (pairs.length < CONFIG.faqMax) {
        const add = el("button", { type: "button", class: "linkish", text: "Add a question" });
        add.addEventListener("click", () => {
          pairs.push({ question: "", answer: "" });
          setValue(name, pairs);
          rerender();
        });
        box.append(add);
      }
      box.append(
        el("p", {
          class: "field-help",
          text: "Answers are drafted strictly from the Harvester's facts.",
        }),
      );
      return fieldShell(name, spec, box);
    }

    case "verified_date": {
      const box = el("div", { id: `f-${name}` }, [
        el("p", { class: "readonly-block", text: value ? String(value) : "not recorded" }),
      ]);
      const button = el("button", {
        type: "button",
        class: "linkish",
        text: "Verify with today's date",
      });
      button.addEventListener("click", () => {
        setValue(name, new Date().toISOString().slice(0, 10));
        rerender();
      });
      box.append(button);
      return fieldShell(name, spec, box);
    }

    case "readonly_date":
    case "readonly_text":
    case "readonly_url":
    case "readonly_image":
      if (value === undefined || value === null || value === "") return null;
      return fieldShell(
        name,
        spec,
        el("p", { class: "readonly-block", text: String(value) }),
      );

    case "readonly_verification":
    case "readonly_change_log":
      if (value === undefined || value === null) return null;
      return fieldShell(name, spec, readonlyBlock(value));

    case "ownership_source": {
      const source = value || {};
      const box = el("div", { id: `f-${name}` });
      const sourceInput = el("input", {
        type: "text",
        id: "f-ownership-source",
        value: source.source || "",
      });
      sourceInput.addEventListener("input", () => {
        setValue("ownership_source.source", sourceInput.value.trim() || null);
      });
      box.append(
        el("div", { class: "field" }, [
          el("label", {
            class: "field-label",
            for: "f-ownership-source",
            text: "source, a URL or a described citation",
          }),
          sourceInput,
        ]),
      );

      const dateInput = el("input", {
        type: "date",
        id: "f-ownership-date",
        value: source.date || new Date().toISOString().slice(0, 10),
      });
      dateInput.addEventListener("input", () => {
        setValue("ownership_source.date", dateInput.value || null);
      });
      box.append(
        el("div", { class: "field" }, [
          el("label", { class: "field-label", for: "f-ownership-date", text: "date" }),
          dateInput,
        ]),
      );

      box.append(
        el("div", { class: "field" }, [
          el("label", {
            class: "field-label",
            for: "f-ownership-method",
            text: "kind of evidence",
          }),
          selectInput(
            "ownership-method",
            "ownership_source.method",
            CONFIG.options.ownership_method,
            source.method,
          ),
        ]),
      );
      return fieldShell(name, spec, box);
    }

    default:
      return fieldShell(name, spec, readonlyBlock(value));
  }
}

function selectOptionKey(name) {
  const map = {
    category: "category",
    cellar_door: "cellar_door",
    fruit_source: "fruit_source",
    production_band: "production_band",
    vessels: "vessels",
    varieties: "varieties",
    wine_styles: "wine_styles",
  };
  return map[name] || name;
}

/* ── Saving — UX.md §1.4, debounced, no save button ────────────────────── */

function queueSave() {
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(save, 600);
}

async function save() {
  if (!state.slug) return;
  const payload = { frontmatter: state.frontmatter, body: state.body };
  try {
    const response = await fetch(`/api/draft/${state.slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      $("#save-state").textContent = `save failed: ${detail.detail || response.status}`;
      $("#save-state").classList.add("warn");
      return;
    }
    const data = await response.json();
    $("#save-state").textContent = `saved ${data.saved}`;
    $("#save-state").classList.remove("warn");
    state.errors = data.errors;
    state.ownershipBlocks = data.ownership_blocks;
    paintErrors();
    renderActions();
    // The preview re-renders on the same debounce as autosave.
    $("#preview").contentWindow.location.replace(`/preview/${state.slug}`);
    refreshQueue();
  } catch (error) {
    $("#save-state").textContent = `save failed: ${error.message}`;
    $("#save-state").classList.add("warn");
  }
}

function paintErrors() {
  // Every failing field shows at once. The pane never reports the first only.
  $$("[data-field]").forEach((wrapper) => {
    wrapper.classList.remove("field-invalid");
    wrapper.querySelectorAll(".field-error").forEach((node) => node.remove());
    const message = state.errors[wrapper.dataset.field];
    if (message) {
      wrapper.classList.add("field-invalid");
      wrapper.append(el("p", { class: "field-error", text: message }));
    }
  });
  const unknown = state.errors._unknown;
  const container = $("#editor-groups");
  container.querySelectorAll(".unknown-field-error").forEach((node) => node.remove());
  if (unknown) {
    container.prepend(el("p", { class: "field-error unknown-field-error", text: unknown }));
  }
}

async function rerender() {
  await save();
  const data = await fetch(`/api/draft/${state.slug}`).then((r) => r.json());
  state.frontmatter = data.frontmatter;
  state.errors = data.errors;
  state.ownershipBlocks = data.ownership_blocks;
  renderEditor(data);
}

/* ── Approve, reject, undo — UX.md §1.4 ────────────────────────────────── */

function renderActions() {
  const approve = $("#approve");
  const reason = $("#action-reason");
  const blocking = [...state.ownershipBlocks];
  const errorCount = Object.keys(state.errors).length;
  if (errorCount) blocking.push(`${errorCount} field${errorCount === 1 ? "" : "s"} fail the schema`);

  approve.disabled = blocking.length > 0;
  // Never a disabled button with no explanation (UX.md §1.5 row 16).
  reason.textContent = blocking.length ? blocking.join(". ") : "";
  reason.className = blocking.length ? "note warn" : "note";
}

function offerUndo(slug) {
  const undo = $("#undo");
  undo.hidden = false;
  undo.textContent = "Undo";
  $("#unpublish").hidden = true;
  clearTimeout(state.undoTimer);
  state.undoTimer = setTimeout(() => {
    undo.hidden = true;
  }, CONFIG.undoSeconds * 1000);
  undo.onclick = async () => {
    const response = await fetch(`/api/draft/${slug}/undo`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      $("#action-reason").textContent = data.blocked;
      $("#action-reason").className = "note warn";
      if (data.offer_unpublish) {
        const unpublish = $("#unpublish");
        unpublish.hidden = false;
        unpublish.onclick = async () => {
          const result = await fetch(`/api/draft/${slug}/unpublish`, { method: "POST" }).then((r) =>
            r.json(),
          );
          refreshQueue(result.rows, result.counts);
          refreshDeployStatus();
          unpublish.hidden = true;
        };
      }
      return;
    }
    undo.hidden = true;
    refreshQueue(data.rows, data.counts);
    refreshDeployStatus();
    loadDraft(slug);
  };
}

function advanceSelection() {
  const rows = $$(".draft-row");
  if (rows.length === 0) {
    state.slug = null;
    state.loaded = false;
    $("#review-body").hidden = true;
    $("#review-empty").hidden = false;
    return;
  }
  selectRow(rows[0]);
}

$("#approve").addEventListener("click", approveCurrent);

async function approveCurrent() {
  if (!state.slug || !state.loaded) return;
  await save();
  const response = await fetch(`/api/draft/${state.slug}/approve`, { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    state.errors = data.errors || {};
    state.ownershipBlocks = data.ownership_blocks || [];
    paintErrors();
    renderActions();
    $("#action-reason").textContent = `${data.blocked}. ${$("#action-reason").textContent}`;
    return;
  }
  const approved = state.slug;
  $("#action-reason").textContent = "Approved.";
  $("#action-reason").className = "note";
  await refreshQueue(data.rows, data.counts);
  // The approve just wrote to _published and regenerated the derived data, so
  // the strip's count is stale the instant this returns.
  refreshDeployStatus();
  offerUndo(approved);
  advanceSelection();
}

$("#reject-open").addEventListener("click", openReject);

function openReject() {
  if (!state.slug) return;
  $("#reject-panel").hidden = false;
  $("#reject-reason").focus();
}

$$("[data-reason]").forEach((button) => {
  button.addEventListener("click", () => {
    $("#reject-reason").value = button.dataset.reason;
  });
});

$("#reject-confirm").addEventListener("click", rejectCurrent);

async function rejectCurrent() {
  if (!state.slug) return;
  const slug = state.slug;
  const response = await fetch(`/api/draft/${slug}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: $("#reject-reason").value }),
  });
  const data = await response.json();
  if (!response.ok) {
    $("#action-reason").textContent = data.blocked;
    $("#action-reason").className = "note warn";
    return;
  }
  $("#reject-panel").hidden = true;
  $("#reject-reason").value = "";
  $("#action-reason").textContent = "Rejected.";
  $("#action-reason").className = "note";
  await refreshQueue(data.rows, data.counts);
  offerUndo(slug);
  advanceSelection();
}

/* ── Keyboard map — UX.md §1.4 ─────────────────────────────────────────── */

const TYPING = new Set(["INPUT", "TEXTAREA", "SELECT"]);

document.addEventListener("keydown", (event) => {
  const typing = TYPING.has(document.activeElement.tagName);

  if (event.key === "Escape") {
    if (!$("#reject-panel").hidden) {
      $("#reject-panel").hidden = true;
      return;
    }
    $$("dialog[open]").forEach((dialog) => dialog.close());
    if (typing) document.activeElement.blur();
    return;
  }

  if (typing) return;
  if (event.metaKey || event.ctrlKey || event.altKey) return;

  switch (event.key) {
    case "ArrowDown":
      event.preventDefault();
      moveSelection(1);
      break;
    case "ArrowUp":
      event.preventDefault();
      moveSelection(-1);
      break;
    case "a":
    case "A":
      // No shortcut approves a draft whose ownership panel has not rendered.
      if (state.loaded && !$("#approve").disabled) approveCurrent();
      break;
    case "r":
    case "R":
      // Without this the same keystroke lands in the reason field the shortcut
      // just focused, and the first-letter preset below then sees a field that
      // is no longer empty.
      event.preventDefault();
      openReject();
      break;
    case "u":
    case "U":
      if (!$("#undo").hidden) $("#undo").click();
      break;
    case "o":
    case "O": {
      const panel = document.getElementById("group-ownership");
      if (panel) {
        panel.scrollIntoView({ block: "start" });
        const first = panel.querySelector("input, select, button");
        if (first) first.focus();
      }
      break;
    }
    case "e":
    case "E": {
      const first = $("#editor-groups").querySelector("input, select, textarea, button");
      if (first) first.focus();
      break;
    }
    case "/":
      event.preventDefault();
      $("#harvest-url").focus();
      break;
    case "?":
      $("#shortcuts").showModal();
      break;
    default:
      break;
  }
});

/* When the reject panel is open, a preset is selectable by its first letter. */
$("#reject-reason").addEventListener("keydown", (event) => {
  if (event.key.length !== 1 || $("#reject-reason").value !== "") return;
  const match = $$("[data-reason]").find(
    (button) => button.dataset.reason[0].toLowerCase() === event.key.toLowerCase(),
  );
  if (match) {
    event.preventDefault();
    $("#reject-reason").value = match.dataset.reason;
  }
});

/* ── The Blocked list — UX.md §1.4.4 ───────────────────────────────────────
 *
 * The actions differ by the source of the reject, deliberately.
 *
 * A DENY-LIST REJECT HAS NO OVERRIDE ACTION. The only route is to correct
 * data/ownership.json, which is hand-maintained and edited in a text editor.
 * The interface never lets a click overrule the deny-list, because the
 * deny-list is the artefact `/validate` check 8 audits against.
 *
 * A harvester signal reject offers `Re-harvest as check`, which re-runs the URL
 * with the machine verdict floored at check so every check rule applies. It
 * downgrades a machine abort to a human decision. It never skips the decision.
 */

async function refreshBlocked() {
  const data = await fetch("/api/blocked").then((r) => r.json());
  const list = $("#blocked-rows");
  list.replaceChildren();
  if (!data.rows || data.rows.length === 0) {
    list.append(
      el("li", {
        class: "empty",
        text:
          "Nothing blocked. Producers stopped by the ownership rule appear here " +
          "with their evidence.",
      }),
    );
    $("#blocked-detail").hidden = true;
    return;
  }
  for (const row of data.rows) {
    const item = el("li", { class: "blocked-row", "data-slug": row.slug, tabindex: "0" }, [
      el("p", { class: "blocked-name", text: row.name || row.slug }),
      el("p", { class: "mono faded", text: row.url }),
      el("p", { class: "mono blocked-reason", text: row.reason }),
    ]);
    if (row.reharvested) {
      item.append(el("p", { class: "mono faded", text: "re-harvested since" }));
    }
    const open = () => showBlocked(row.slug);
    item.addEventListener("click", open);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    list.append(item);
  }
}

async function showBlocked(slug) {
  const record = await fetch(`/api/blocked/${slug}`).then((r) => r.json());
  const detail = $("#blocked-detail");
  detail.hidden = false;
  detail.replaceChildren();

  if (record.unreadable) {
    detail.append(el("p", { class: "field-error", text: record.unreadable }));
    return;
  }

  // The same signals table and deny-list block the review pane uses, read-only.
  const fauxPanel = {
    ...record,
    chip: "REJECT",
    populated: (record.signals || []).filter((row) => row.populated).length,
    abn_display: {},
    resolutions: [],
    signal_labels: Object.fromEntries(
      (record.signals || []).map((row) => [row.key, row.key.replace(/_/g, " ")]),
    ),
    check_labels: { name: "name", domain: "domain", abn: "ABN" },
  };
  detail.append(
    el("p", { class: "ownership-basis", text: record.basis || "" }),
    el("p", {
      class: "mono mono-caps",
      text: `Deny-list, data/ownership.json (updated ${record.deny_list.updated || "undated"})`,
    }),
  );
  const body = el("tbody");
  for (const row of record.deny_list.rows) {
    for (const node of denyListRow(row, fauxPanel.check_labels, null)) body.append(node);
  }
  detail.append(el("table", { class: "deny-table" }, [body]));

  const signalBody = el("tbody");
  for (const row of record.signals || []) {
    const cell = el("td", {});
    if (!row.populated) cell.append(el("p", { class: "faded", text: "nothing extracted" }));
    else for (const item of row.items) cell.append(el("p", { class: "quote", text: `"${item}"` }));
    signalBody.append(
      el("tr", {}, [el("td", { class: "mono", text: row.key.replace(/_/g, " ") }), cell]),
    );
  }
  detail.append(
    el("p", { class: "mono mono-caps", text: "Ownership signals" }),
    el("table", { class: "signal-table" }, [signalBody]),
  );

  const actions = el("div", { class: "blocked-actions" });
  if (record.source_of_reject === "deny-list") {
    actions.append(
      el("p", {
        class: "note",
        text:
          "This was a deny-list block. There is no override here. Correct " +
          "data/ownership.json, then re-harvest so the corrected deny-list is " +
          "what decides.",
      }),
      el("button", {
        type: "button",
        class: "btn btn-quiet",
        id: "blocked-open-json",
        text: "Open data/ownership.json",
      }),
      el("button", {
        type: "button",
        class: "btn btn-quiet",
        id: "blocked-reharvest",
        text: "Re-harvest",
      }),
    );
  } else {
    actions.append(
      el("p", {
        class: "note",
        text:
          "This was the Harvester's own signal-based reject. Re-harvesting as " +
          "check puts the draft in the queue with every check rule applying: a " +
          "source is required and every signal must be resolved.",
      }),
      el("button", {
        type: "button",
        class: "btn btn-quiet",
        id: "blocked-reharvest-check",
        text: "Re-harvest as check",
      }),
    );
  }
  detail.append(actions);

  const reharvest = async (action) => {
    const response = await fetch(`/api/blocked/${slug}/reharvest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!response.ok) {
      const problem = await response.json();
      detail.append(el("p", { class: "field-error", text: problem.detail }));
      return;
    }
    await refreshBlocked();
    fetch("/api/harvest/queue")
      .then((r) => r.json())
      .then(renderHarvestQueue);
  };
  const openJson = $("#blocked-open-json");
  if (openJson) openJson.addEventListener("click", () => $("#ownership-open").click());
  const plain = $("#blocked-reharvest");
  if (plain) plain.addEventListener("click", () => reharvest("reharvest"));
  const asCheck = $("#blocked-reharvest-check");
  if (asCheck) asCheck.addEventListener("click", () => reharvest("reharvest-as-check"));
}

/* ── Dialogs ───────────────────────────────────────────────────────────── */

$("#shortcuts-open").addEventListener("click", () => $("#shortcuts").showModal());

$("#ownership-open").addEventListener("click", async () => {
  const response = await fetch("/api/ownership");
  const text = response.ok
    ? JSON.stringify(await response.json(), null, 2)
    : "data/ownership.json is not present.";
  $("#ownership-json").textContent = text;
  $("#ownership-viewer").showModal();
});

$$("dialog [data-close]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog").close());
});

/* ── Start ─────────────────────────────────────────────────────────────── */

bindRows();
startLogStream();
fetch("/api/harvest/queue")
  .then((r) => r.json())
  .then(renderHarvestQueue);
refreshBlocked();

const firstRow = $(".draft-row");
if (firstRow) selectRow(firstRow);
