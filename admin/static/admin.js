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
    list.append(
      el("li", { class: "harvest-row" }, [
        el("p", { class: "mono", title: item.url }, [
          el("span", { class: `state state-${item.state.toLowerCase()}`, text: item.state }),
          el("span", { text: ` ${index + 1}. ${shortened}` }),
        ]),
        item.detail ? el("p", { class: "mono warn", text: item.detail }) : null,
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
}

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

function renderEditor(data) {
  const container = $("#editor-groups");
  container.replaceChildren();

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
          text: `Determination: ${data.ownership_chip}. The verdict, the deny-list rows and the signals table land at Gate 4.`,
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
          unpublish.hidden = true;
        };
      }
      return;
    }
    undo.hidden = true;
    refreshQueue(data.rows, data.counts);
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

const firstRow = $(".draft-row");
if (firstRow) selectRow(firstRow);
