"""Terminal styling for human-facing CLI output (A9-06).

Scope and guarantees:

- stdlib only; SGR styling is applied only when sys.stdout.isatty() and
  TERM != "dumb" and NO_COLOR is unset and the resolved theme is not "plain";
- machine-readable output is never touched: --version, --json, hook_cli
  protocol output, evidence, and lifecycle logs never route through this
  module;
- themes are cosmetic only (light/dark/auto/plain) and have zero governance
  effect: no guard, evidence, approval, hook, or lifecycle code imports this
  module;
- the CLI version string is sourced solely from madclaude.version.__version__;
  this module contains no version literal.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, TextIO

THEMES = ("auto", "light", "dark", "plain")

_SGR = {
    "dark": {
        "heading": "1;36",
        "key": "36",
        "ok": "32",
        "warn": "33",
        "error": "31",
        "dim": "2",
    },
    "light": {
        "heading": "1;34",
        "key": "34",
        "ok": "32",
        "warn": "33",
        "error": "31",
        "dim": "2",
    },
}
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def resolve_theme(requested: str | None = None) -> str:
    value = (requested or os.environ.get("MADCLAUDE_THEME") or "auto").strip().lower()
    if value not in THEMES:
        return "auto"
    return value


def styling_enabled(theme: str, stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    resolved = resolve_theme(theme)
    if resolved == "plain":
        return False
    if not stream.isatty():
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    if "NO_COLOR" in os.environ:
        return False
    return True


def style(text: str, role: str, *, theme: str = "auto", stream: TextIO | None = None) -> str:
    resolved = _effective_theme(theme)
    if not styling_enabled(resolved, stream):
        return text
    code = _SGR[resolved].get(role)
    if not code:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def _effective_theme(theme: str) -> str:
    resolved = resolve_theme(theme)
    if resolved != "auto":
        return resolved
    colorfgbg = os.environ.get("COLORFGBG", "")
    background = colorfgbg.split(";")[-1] if colorfgbg else ""
    if background in {"7", "15"}:
        return "light"
    return "dark"


def strip_ansi(text: str) -> str:
    return _ANSI_PATTERN.sub("", text)
