---
name: gate-exit
description: The procedure for closing a build gate. Use when a gate's work appears finished, when about to claim a gate is done, when asked whether a gate can close, or before requesting approval to start the next gate. Also use before any deploy.
---

# Gate exit

CLAUDE.md rule 1: gates are sequential and blocking. A gate closes when its done-condition **passes and has been seen to pass**, not when the work feels finished.

This skill reports. It does not fix, and it does not close the gate — closing is the user's call after you summarise.

## Procedure

### 1. Re-read the gate's done-condition from CLAUDE.md

Verbatim. Not from memory, not from the plan file. The done-condition is a list of semicolon-separated conditions; treat each as a separate item you must be able to point at evidence for.

### 2. Run `/validate`

Every check listed for this gate **and every earlier gate** must pass. `/validate` reports; it never fixes. If it prints `VALIDATE FAIL`, the gate does not close — report the failures and stop.

### 3. Exercise the falsifiable conditions

Nearly every gate's done-condition names a **deliberately corrupted fixture**. This is the part that gets skipped and it is the part that matters. For each one:

1. Build the fixture that violates the condition.
2. Run the check.
3. **Confirm it fails, and that the error names the actual problem** — a check that fails with an unrelated stack trace has not been verified.
4. Restore.

A done-condition you cannot make fail has not been tested. Say so rather than counting it.

Where the check has a module self-test (`errors = _selftest() + run()`), the fixture is already mechanised and runs on every invocation — confirm the self-test exists and covers the condition, rather than doing it by hand.

### 4. Screenshot any visual work

CLAUDE.md working style: take the screenshot **before** claiming visual work is done. Both light and dark mode. Check it against DESIGN.md §10 and its own test question. If you are unsure whether something meets DESIGN.md, it doesn't — ask. Load the `design-reviewer` agent for anything touching presentation.

### 5. Check the commits

Small commits per logical unit, imperative messages, gate-prefixed (`Gate 4: …`). Each new `/validate` check should be its own commit, landed right after the feature it guards. No drive-by refactors mixed in.

### 6. Report

Walk the done-conditions in order. For each: the condition, what you ran, what you saw.

Then one of:

- **`GATE N READY`** — every condition demonstrated, with the evidence above.
- **`GATE N BLOCKED`** — with the specific conditions not met and why.

Never report ready with caveats. A condition that is "basically working" or "passes except for" is not met. Partial completion is reported as blocked with a list, and it is the user's decision whether to accept it — not yours.

## Do not

- Do not fix things during this procedure. Report, then fix as separate work, then re-run.
- Do not start the next gate's work. Not even a small piece, not even while you're in there.
- Do not soften a done-condition because it turned out to be awkward. If a condition is genuinely wrong, say so and propose an amendment — CLAUDE.md's habit is to annotate superseded conditions in place with a date, never to delete or quietly reinterpret them.
- Do not count "the code exists" as "the condition passes."
