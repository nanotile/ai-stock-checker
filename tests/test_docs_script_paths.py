"""Docs-gate: script paths + CLI flags cited in active docs must be real.

Adapted from tradermonty docs-gate (#555 / #498) — refuse advertised
``scripts/…`` paths that are missing, and refuse ``--flags`` on those
commands that the script (or its ``"$@"`` Python target) does not accept.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Active human/agent docs (not history digests / changelog archaeology).
DOC_GLOBS = (
    "README.md",
    "FRIENDS.md",
    "AGENTS.md",
    "AUTOPILOT.md",
    "DOCS_MAINTENANCE.md",
    "OPENBB.md",
    "GIT.md",
    "RELEASES.md",
    "DESIGN.md",
    "GITHUB_WATCH.md",
    "docs/LAYA.md",
    "docs/PROMOTE_AB.md",
)

# scripts/foo.py · scripts/bar.sh · optional leading ./
_SCRIPT_RE = re.compile(
    r"(?:^|[\s`'\"(])/?(?:\.\/)?(scripts/[A-Za-z0-9_./-]+\.(?:py|sh))\b"
)

# Long options after a script cite on the same line (group 1 = script, 2 = tail).
_SCRIPT_WITH_TAIL_RE = re.compile(
    r"(?:^|[\s`'\"(])/?(?:\.\/)?(scripts/[A-Za-z0-9_./-]+\.(?:py|sh))"
    r"([^\n`]*)"
)

_FLAG_RE = re.compile(r"(?<![\w-])(--[A-Za-z][A-Za-z0-9-]*)\b")

# Python argparse long options.
_PY_ADD_ARG_RE = re.compile(
    r"""add_argument\(\s*['"](--[A-Za-z][A-Za-z0-9-]*)['"]"""
)

# Shell wrappers that forward argv to a Python script.
_SH_WRAP_PY_RE = re.compile(
    r"""(?:python3?|exec\s+python3?)\s+"""
    r"""(?:"?\$ROOT/|"?)(scripts/[A-Za-z0-9_./-]+\.py)"""
)

# Native shell long options: [[ "$1" == "--tick" ]] / case --force)
_SH_EQ_FLAG_RE = re.compile(
    r"""\[\[\s*"\$\{?1(?::-)?\}?"\s*==\s*['"](--[A-Za-z][A-Za-z0-9-]*)['"]"""
)
_SH_CASE_FLAG_RE = re.compile(r"""(--[A-Za-z][A-Za-z0-9-]*)\)""")


def _iter_doc_files() -> list[Path]:
    out: list[Path] = []
    for rel in DOC_GLOBS:
        path = ROOT / rel
        if path.is_file():
            out.append(path)
    return out


def documented_script_paths() -> dict[str, set[str]]:
    """Map relative script path → set of docs that cite it."""
    found: dict[str, set[str]] = {}
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8")
        rel_doc = str(path.relative_to(ROOT))
        for match in _SCRIPT_RE.finditer(text):
            script = match.group(1)
            found.setdefault(script, set()).add(rel_doc)
    return found


def documented_script_flags() -> dict[tuple[str, str], set[str]]:
    """Map (script, --flag) → docs that advertise that flag after the script."""
    found: dict[tuple[str, str], set[str]] = {}
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8")
        rel_doc = str(path.relative_to(ROOT))
        for match in _SCRIPT_WITH_TAIL_RE.finditer(text):
            script = match.group(1)
            tail = match.group(2) or ""
            for flag in _FLAG_RE.findall(tail):
                found.setdefault((script, flag), set()).add(rel_doc)
    return found


def _python_flags(script_rel: str) -> set[str]:
    path = ROOT / script_rel
    if not path.is_file():
        return set()
    return set(_PY_ADD_ARG_RE.findall(path.read_text(encoding="utf-8")))


def _shell_flags(script_rel: str) -> set[str]:
    path = ROOT / script_rel
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    flags: set[str] = set(_SH_EQ_FLAG_RE.findall(text))
    flags.update(_SH_CASE_FLAG_RE.findall(text))
    wrap = _SH_WRAP_PY_RE.search(text)
    if wrap:
        flags.update(_python_flags(wrap.group(1)))
    # Common: python3 "$ROOT/scripts/foo.py" "$@"
    for m in re.finditer(
        r'''["']?\$ROOT/(scripts/[A-Za-z0-9_./-]+\.py)["']?''', text
    ):
        flags.update(_python_flags(m.group(1)))
    return flags


def accepted_flags(script_rel: str) -> set[str]:
    if script_rel.endswith(".py"):
        return _python_flags(script_rel)
    if script_rel.endswith(".sh"):
        return _shell_flags(script_rel)
    return set()


def test_documented_script_paths_exist() -> None:
    cited = documented_script_paths()
    assert cited, "expected at least one scripts/… citation in active docs"
    missing = sorted(
        script for script in cited if not (ROOT / script).is_file()
    )
    assert not missing, (
        "docs cite missing scripts (tradermonty docs-gate): "
        + "; ".join(
            f"{s} (in {', '.join(sorted(cited[s]))})" for s in missing
        )
    )


def test_documented_script_flags_are_accepted() -> None:
    cited = documented_script_flags()
    # FRIENDS / PROMOTE_AB / AUTOPILOT / GITHUB_WATCH advertise real flags.
    assert cited, "expected at least one scripts/… --flag citation in active docs"
    bad: list[str] = []
    for (script, flag), docs in sorted(cited.items()):
        accepted = accepted_flags(script)
        if flag not in accepted:
            bad.append(
                f"{script} {flag} (in {', '.join(sorted(docs))}; "
                f"accepted={sorted(accepted) or ['<none>']})"
            )
    assert not bad, (
        "docs cite flags the script does not accept (tradermonty docs-gate): "
        + "; ".join(bad)
    )


def test_docs_gate_scans_core_files() -> None:
    files = {str(p.relative_to(ROOT)) for p in _iter_doc_files()}
    assert "README.md" in files
    assert "FRIENDS.md" in files
    assert "AGENTS.md" in files


def test_accepted_flags_resolve_shell_wrapper() -> None:
    flags = accepted_flags("scripts/run_clean_code_agent.sh")
    assert "--apply" in flags
    assert "--force" in accepted_flags("scripts/run_github_watch_once.sh")
    assert "--tick" in accepted_flags("scripts/watchdog.sh")
    assert "--since" in accepted_flags("scripts/summarize_trades.py")
