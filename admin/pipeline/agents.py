"""agents.py — the model call, its two retry tiers, and the token ledger. Gate 5.

TRD.md §7.2 and §7.3.

── Why the prompts are not in this file ──────────────────────────────────────

Every prompt is loaded from ``PROMPTS/*.md`` at call time. **A prompt string
literal in a ``.py`` file is a defect** (TRD.md §7.2). The editorial guardrails
are the most-edited text in the project and the part a non-programmer most needs
to be able to read and change; putting them in source would make every wording
change a code change and a diff nobody reviews properly.

``load_prompt`` therefore re-reads from disk on every call. No caching. The cost
is a few microseconds and the benefit is that editing a prompt takes effect on
the next harvest without restarting the admin app.

── The two tiers, and why there are exactly two ──────────────────────────────

The SDK client is built with ``max_retries=0`` so that the one mandated retry is
ours and the operator watches it happen in the log pane. A vendor SDK quietly
retrying three times behind a spinner is the opposite of what UX.md §1.2 asks of
this system.

**Transport tier** — ``RateLimitError``, a 5xx ``APIStatusError``, or
``APIConnectionError``. One retry, logged with the reason and any ``retry-after``,
then ``AgentError``. A sub-500 status error raises immediately: a 400 is a bad
request and will be exactly as bad the second time.

**Content tier** — output that fails the stage's ``validate`` callable. One
re-ask with the validation error appended, then ``MalformedOutput`` carrying the
raw text, which is written to ``temp_data/failed/`` and named in the log. Never
silently discarded (UX.md §1.5 row 4).

One retry each, and no more. A pipeline that retries until something parses is a
pipeline that eventually publishes whatever finally parsed.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from admin.config import (  # noqa: E402
    ANTHROPIC_API_KEY,
    FAILED_DIR,
    PROMPTS_DIR,
)

Logger = Callable[[str, str], None]


def _null_log(level: str, message: str) -> None:
    """Default logger. The pipeline is usable from a CLI with no log pane."""


# =============================================================================
# 1. Errors
# =============================================================================


class AgentError(Exception):
    """Transport tier exhausted, or the call cannot be made at all."""


class MalformedOutput(Exception):
    """Content tier exhausted. Carries the raw text and where it was saved."""

    def __init__(self, message: str, *, stage: str, raw: str, path: Path | None = None):
        super().__init__(message)
        self.stage = stage
        self.raw = raw
        self.path = path


# =============================================================================
# 2. Prompts — loaded at call time, never embedded (TRD.md §7.2)
# =============================================================================

#: ``{{NAME}}``. Deliberately not str.format: prompt files are full of literal
#: braces (the Harvester prompt contains a JSON skeleton), and ``format`` would
#: either explode on them or force the prompts to be written with doubled braces,
#: which would make the most-read text in the project harder to read.
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def prompt_path(name: str) -> Path:
    return PROMPTS_DIR / f"{name}.md"


def load_prompt(name: str, **values: Any) -> str:
    """Read ``PROMPTS/<name>.md`` and substitute ``{{PLACEHOLDER}}`` values.

    Re-read on every call, deliberately: see the module docstring.

    An unfilled placeholder raises rather than reaching the model as literal
    ``{{PAGE_TEXT}}``, which would produce a confidently wrong answer about
    nothing and cost a full run to notice.
    """
    path = prompt_path(name)
    if not path.is_file():
        raise AgentError(f"prompt not found: PROMPTS/{name}.md")
    text = path.read_text(encoding="utf-8")

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise AgentError(f"PROMPTS/{name}.md has no value for {{{{{key}}}}}")
        return str(values[key])

    filled = _PLACEHOLDER.sub(substitute, text)
    return filled


# =============================================================================
# 3. The token ledger — TRD.md §7.3, UX.md §1.2
#
# "Token usage prints once per item, at the end. Cost visibility is a
# requirement at 150 to 300 producers."
# =============================================================================


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


def _short(count: int) -> str:
    """4123 -> '4.1k'. The log pane is read at a glance, not audited in it."""
    if count < 1000:
        return str(count)
    return f"{count / 1000:.1f}k"


@dataclass
class Ledger:
    """Per-item token accounting, in call order."""

    stages: list[tuple[str, Usage]] = field(default_factory=list)

    def record(self, stage: str, usage: Usage) -> None:
        self.stages.append((stage, usage))

    def total(self) -> Usage:
        out = Usage()
        for _, usage in self.stages:
            out = out + usage
        return out

    def line(self) -> str:
        """`tokens in/out: harvester 4.1k/1.2k, architect 3.0k/2.4k` (UX.md §1.2)."""
        if not self.stages:
            return "tokens in/out: none"
        parts = [
            f"{stage} {_short(u.input_tokens)}/{_short(u.output_tokens)}"
            for stage, u in self.stages
        ]
        return "tokens in/out: " + ", ".join(parts)

    def total_line(self, label: str = "run total") -> str:
        total = self.total()
        return (
            f"{label} tokens in/out: "
            f"{_short(total.input_tokens)}/{_short(total.output_tokens)}"
        )


# =============================================================================
# 4. The client
#
# Injectable, because the pipeline has to be testable without a network or a
# key. `set_client` is what the fixture harness uses; nothing in the app calls
# it. The real client is built lazily so that importing this module — which
# `/validate` and the admin app both do — never requires a key.
# =============================================================================

_client: Any = None
_client_built = False


def set_client(client: Any) -> None:
    """Inject a client. Used by the fixture harness; never by the app."""
    global _client, _client_built
    _client = client
    _client_built = True


def get_client() -> Any:
    global _client, _client_built
    if _client_built:
        if _client is None:
            raise AgentError(
                "ANTHROPIC_API_KEY is not set. Add it to .env; nothing else in "
                "the admin app needs it, but every pipeline stage does."
            )
        return _client
    if not ANTHROPIC_API_KEY:
        _client_built = True
        _client = None
        raise AgentError(
            "ANTHROPIC_API_KEY is not set. Add it to .env; nothing else in the "
            "admin app needs it, but every pipeline stage does."
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - requirements.txt pins it
        raise AgentError(f"the anthropic SDK is not installed: {exc}") from exc

    # max_retries=0 so the single mandated retry is ours and is visible.
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=0)
    _client_built = True
    return _client


def _error_classes() -> tuple[Any, Any, Any]:
    """The three typed errors the transport tier discriminates on.

    Imported lazily and defensively: this module must import cleanly with no SDK
    present so `/validate` and the fixture harness can run in a bare checkout.
    """
    try:
        import anthropic

        return (
            anthropic.RateLimitError,
            anthropic.APIStatusError,
            anthropic.APIConnectionError,
        )
    except ImportError:  # pragma: no cover

        class _Never(Exception):
            pass

        return (_Never, _Never, _Never)


def _retry_after(exc: Any) -> str:
    """`retry-after` where the header carries it (TRD.md §7.3)."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    try:
        value = headers.get("retry-after")
    except Exception:  # pragma: no cover - a header mapping that is not a mapping
        return ""
    return f", retry-after {value}s" if value else ""


def _status_of(exc: Any) -> int | None:
    for attribute in ("status_code", "status"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


# =============================================================================
# 5. Fence stripping
#
# TRD.md §7.1: "A single markdown fence is stripped rather than being allowed to
# burn the one re-ask on formatting." A model wrapping valid JSON in ```json is
# not a content failure worth spending the one re-ask on.
# =============================================================================

_FENCE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def strip_fence(text: str) -> str:
    match = _FENCE.match(text)
    return match.group(1) if match else text.strip()


# =============================================================================
# 6. The call
# =============================================================================


def _text_of(message: Any) -> str:
    parts = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _usage_of(message: Any) -> Usage:
    usage = getattr(message, "usage", None)
    return Usage(
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def save_failed(stage: str, slug: str, raw: str) -> Path:
    """`temp_data/failed/{slug}-{stage}-{time}.txt` (UX.md §1.5 row 4)."""
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = FAILED_DIR / f"{slug or 'unknown'}-{stage}-{stamp}.txt"
    path.write_text(raw, encoding="utf-8")
    return path


def _send(client: Any, model: str, prompt: str, max_tokens: int) -> Any:
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


def call(
    stage: str,
    model: str,
    prompt: str,
    *,
    validate: Callable[[str], Any],
    log: Logger = _null_log,
    ledger: Ledger | None = None,
    slug: str = "",
    max_tokens: int = 8000,
    client: Any = None,
) -> Any:
    """One agent call, both retry tiers, and the token record.

    ``validate`` receives the model's text and returns the parsed value, or
    raises ``ValueError`` with a message the re-ask can act on. It is the
    stage's own contract: JSON shape for the Harvester, parseable MDX for the
    other two.

    Returns whatever ``validate`` returns. Raises ``AgentError`` when the
    transport tier is exhausted and ``MalformedOutput`` when the content tier is.

    The model id is printed to the log as read from `.env`, never hardcoded
    (CLAUDE.md stack constraints). The API key is never logged.
    """
    client = client if client is not None else get_client()
    rate_limit_error, status_error, connection_error = _error_classes()

    def attempt(text_prompt: str) -> tuple[str, Usage]:
        """One transport-tier-protected send. Returns (text, usage)."""
        for is_retry in (False, True):
            try:
                message = _send(client, model, text_prompt, max_tokens)
                return _text_of(message), _usage_of(message)
            except rate_limit_error as exc:
                if is_retry:
                    raise AgentError(f"{stage}: rate limited twice, giving up") from exc
                log(
                    "warn",
                    f"{stage}: rate limited{_retry_after(exc)}, retrying once",
                )
            except connection_error as exc:
                if is_retry:
                    raise AgentError(f"{stage}: connection failed twice: {exc}") from exc
                log("warn", f"{stage}: connection error ({exc}), retrying once")
            except status_error as exc:
                status = _status_of(exc)
                # A sub-500 will not fix itself. Raise now rather than spend the
                # retry proving it.
                if status is not None and status < 500:
                    raise AgentError(f"{stage}: API status {status}, not retryable") from exc
                if is_retry:
                    raise AgentError(f"{stage}: API status {status} twice, giving up") from exc
                log(
                    "warn",
                    f"{stage}: API status {status}{_retry_after(exc)}, retrying once",
                )
        raise AgentError(f"{stage}: transport retry fell through")  # pragma: no cover

    total = Usage()
    text, usage = attempt(prompt)
    total = total + usage

    try:
        result = validate(strip_fence(text))
    except ValueError as first_error:
        # ── Content tier: one re-ask, with the error appended ──────────────
        log("warn", f"{stage}: {first_error}, re-asking once")
        reask = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"Your previous response could not be used. The error was:\n\n"
            f"{first_error}\n\n"
            f"Return corrected output only."
        )
        text, usage = attempt(reask)
        total = total + usage
        try:
            result = validate(strip_fence(text))
        except ValueError as second_error:
            path = save_failed(stage, slug, text)
            if ledger is not None:
                ledger.record(stage, total)
            log(
                "error",
                f"{stage}: {second_error} after one re-ask. "
                f"Raw output saved to {path.parent.name}/{path.name}",
            )
            raise MalformedOutput(
                f"{stage}: {second_error}", stage=stage, raw=text, path=path
            ) from second_error

    if ledger is not None:
        ledger.record(stage, total)
    return result
