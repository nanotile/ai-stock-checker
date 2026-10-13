"""Docs-gate: script paths cited in active docs must exist on disk.

Adapted from tradermonty docs-gate (#555 / #498) — refuse advertised
``scripts/…`` paths that are missing so friends do not copy a dead command.
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


def test_docs_gate_scans_core_files() -> None:
    files = {str(p.relative_to(ROOT)) for p in _iter_doc_files()}
    assert "README.md" in files
    assert "FRIENDS.md" in files
    assert "AGENTS.md" in files
