"""Fasst einen Lauf für die GitHub-Actions-Zusammenfassung zusammen.

    python tools/summary.py site >> "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(run: dict) -> str:
    aufloesung = "Tageswerte" if run.get("resolution") == "daily" else "Monatsmittel"
    werte = f"{run.get('values', 0):,}".replace(",", ".")
    lines = [
        "### Seetemperaturen",
        "",
        f"- Quelle: **{run.get('source', '?')}**"
        + ("  ⚠️ **Demodaten, keine Messwerte**" if run.get("is_demo") else ""),
        f"- Auflösung: {aufloesung}",
        f"- Bezugszeitraum: {run.get('reference', '?')} ({run.get('method', '?')})",
        f"- Datenstand: {run.get('data_until', '?')} — {werte} Werte, "
        f"{len(run.get('lakes', []))} Seen",
        f"- {len(run.get('files', []))} PNG-Dateien erzeugt",
    ]
    recent = run.get("recent") or {}
    if recent:
        lines.insert(-1, f"- Letzte {recent.get('hours', '?')} h: "
                         f"{recent.get('values', '?')} Einzelmessungen aus "
                         f"{recent.get('lakes', '?')} Seen "
                         f"(bis {recent.get('until', '?')})")
    lines += [f"- Übersprungen: {item}" for item in run.get("skipped", [])]
    notes = run.get("notes", [])
    if notes:
        lines += ["", "<details><summary>Hinweise der Quelle</summary>", ""]
        lines += [f"- {note}" for note in notes[:20]]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest = args.directory / "run.json"
    if not manifest.is_file():
        raise SystemExit(f"{manifest} fehlt.")
    print(render(json.loads(manifest.read_text(encoding="utf-8"))), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
