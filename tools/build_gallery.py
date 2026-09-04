"""Baut aus einem Ausgabeverzeichnis eine Übersichtsseite für den Browser.

Die Seite ist für das Handy gedacht: eine Spalte, Bilder in voller Breite,
Antippen öffnet die Datei in Originalgrösse. Liegen beide Farbschemata vor,
wählt der Browser über ``prefers-color-scheme`` selbst -- die Seite folgt
also der Systemeinstellung, ohne Schalter und ohne JavaScript.

Aufruf::

    python tools/build_gallery.py output/          # schreibt output/index.html
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path

# Reihenfolge und Beschriftung der Übersichtsgrafiken.
OVERVIEW = [
    ("01_uebersicht_abweichung", "Alle Seen im Vergleich",
     "Mittlere Abweichung der Badesaison vom langjährigen Normalwert."),
    ("02_monatsmatrix", "Monat für Monat",
     "Wo im Jahr die Abweichung entstanden ist -- je See und Monat."),
    ("03_badetage", "Badetage",
     "Wie viele Tage warm genug waren, gemessen am langjährigen Mittel."),
    ("04_saisonabweichung_zeitreihe", "Jeder Sommer seit Reihenbeginn",
     "Ein Balken je Jahr und See -- der lange Blick auf die Entwicklung."),
]

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #fcfcfb; --card: #ffffff; --line: #e6e5e1;
  --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a8983;
  --accent: #2a78d6; --warn-bg: #fdf3e7; --warn-line: #eda100; --warn-ink: #6b4a05;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a19; --card: #242422; --line: #333330;
    --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8f8e85;
    --accent: #3987e5; --warn-bg: #2e2716; --warn-line: #c98500; --warn-ink: #f0d9a8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 16px 64px;
  background: var(--bg); color: var(--ink);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-text-size-adjust: 100%;
}
main { max-width: 900px; margin: 0 auto; }
header { padding: 28px 0 8px; }
h1 { margin: 0 0 6px; font-size: 1.55rem; line-height: 1.2; letter-spacing: -0.01em; }
h2 { margin: 40px 0 2px; font-size: 1.1rem; letter-spacing: -0.005em; }
h2:first-of-type { margin-top: 28px; }
p { margin: 0 0 4px; }
.lede { color: var(--ink-2); }
.caption { color: var(--ink-3); font-size: 0.9rem; margin-bottom: 10px; }
.meta {
  margin: 16px 0 0; padding: 14px 16px;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  font-size: 0.9rem;
}
.meta dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; margin: 0; }
.meta dt { color: var(--ink-3); }
.meta dd { margin: 0; color: var(--ink); }
.warn {
  margin: 18px 0 0; padding: 14px 16px;
  background: var(--warn-bg); border: 1px solid var(--warn-line);
  border-left-width: 4px; border-radius: 10px; color: var(--warn-ink);
}
.warn strong { display: block; margin-bottom: 3px; }
figure { margin: 0 0 8px; }
figure a { display: block; }
img {
  width: 100%; height: auto; display: block;
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
}
.lakes { margin-top: 8px; }
footer {
  margin-top: 48px; padding-top: 18px; border-top: 1px solid var(--line);
  color: var(--ink-3); font-size: 0.85rem;
}
a { color: var(--accent); }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.92em; }
.hint { color: var(--ink-3); font-size: 0.85rem; margin: 14px 0 0; }
ul.notes { margin: 6px 0 0; padding-left: 20px; color: var(--ink-3); font-size: 0.85rem; }
"""


def picture(light: str | None, dark: str | None, alt: str) -> str:
    """Bild mit automatischer Hell/Dunkel-Wahl, wenn beide Fassungen da sind."""
    primary = light or dark
    if primary is None:
        return ""
    alt = html.escape(alt, quote=True)
    if light and dark:
        inner = (
            f'<source media="(prefers-color-scheme: dark)" srcset="{dark}">'
            f'<img src="{light}" alt="{alt}" loading="lazy">'
        )
        img = f"<picture>{inner}</picture>"
    else:
        img = f'<img src="{primary}" alt="{alt}" loading="lazy">'
    return f'<figure><a href="{primary}">{img}</a></figure>'


def find(root: Path, relative: str) -> str | None:
    return relative if (root / relative).is_file() else None


def collect(root: Path, run: dict) -> tuple[list, list]:
    year = run.get("year", "")
    overview = []
    for prefix, title, caption in OVERVIEW:
        stem = f"{prefix}_{year}.png" if prefix != "04_saisonabweichung_zeitreihe" \
            else f"{prefix}.png"
        light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
        if light or dark:
            overview.append((title, caption, light, dark))

    lakes = []
    for lake in run.get("lakes", []):
        stem = f"seen/{lake['key']}_{year}.png"
        light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
        if light or dark:
            lakes.append((lake["name"], light, dark))
    return overview, lakes


def render(root: Path, run: dict) -> str:
    esc = lambda v: html.escape(str(v))
    overview, lakes = collect(root, run)
    year = run.get("year", "")
    generated = datetime.fromisoformat(run["generated_at"]).strftime("%d.%m.%Y, %H:%M UTC")
    aufloesung = "Tageswerte" if run.get("resolution") == "daily" else "Monatsmittel"
    werte = f"{run.get('values', 0):,}".replace(",", ".")

    banner = ""
    if run.get("is_demo"):
        banner = (
            '<div class="warn"><strong>Demodaten — keine Messwerte.</strong>'
            "Diese Auswertung beruht auf einem synthetischen Jahresgangmodell und "
            "sagt nichts über die tatsächlichen Seen aus. Für echte Werte den Lauf "
            "mit der Quelle <code>ehyd</code> starten.</div>"
        )

    skipped = "".join(
        f"<li>Übersprungen: {esc(item)}</li>" for item in run.get("skipped", [])
    )
    notes = "".join(f"<li>{esc(note)}</li>" for note in run.get("notes", [])[:6])
    notes_block = f'<ul class="notes">{skipped}{notes}</ul>' if (skipped or notes) else ""

    parts = [
        "<!doctype html>",
        '<html lang="de"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Kärntner Seen {esc(year)} — Wassertemperatur</title>",
        f"<style>{STYLE}</style></head><body><main>",
        "<header>",
        f"<h1>Kärntner Seen {esc(year)}</h1>",
        '<p class="lede">Wassertemperatur im Vergleich zum langjährigen Mittel '
        f'{esc(run.get("reference", ""))}.</p>',
        "</header>",
        banner,
        '<div class="meta"><dl>',
        f"<dt>Quelle</dt><dd>{esc(run.get('source', ''))}</dd>",
        f"<dt>Auflösung</dt><dd>{aufloesung}</dd>",
        f"<dt>Normalwert</dt><dd>{esc(run.get('method', ''))} über "
        f"{esc(run.get('reference', ''))}</dd>",
        f"<dt>Datenstand</dt><dd>{esc(run.get('data_until', ''))} "
        f"({werte} Werte ab {esc(run.get('data_from', ''))})</dd>",
        f"<dt>Erzeugt</dt><dd>{esc(generated)}</dd>",
        f"</dl>{notes_block}</div>",
        '<p class="hint">Antippen öffnet ein Bild in voller Auflösung.</p>',
    ]

    for title, caption, light, dark in overview:
        parts += [f"<h2>{esc(title)}</h2>", f'<p class="caption">{esc(caption)}</p>',
                  picture(light, dark, title)]

    if lakes:
        parts += ['<h2 class="lakes">Jahresgang je See</h2>',
                  '<p class="caption">Der Verlauf des Jahres gegen den Normalwert, '
                  'das Band zeigt die Bandbreite des Bezugszeitraums.</p>']
        for name, light, dark in lakes:
            parts += [f'<p class="caption" style="margin-top:14px">{esc(name)}</p>',
                      picture(light, dark, name)]

    parts += [
        "<footer>",
        "Erzeugt mit <a href=\"https://github.com/mgorfer/lake-temperature\">seetemp</a>. ",
        "Die Seite folgt der Hell/Dunkel-Einstellung des Geräts. ",
        'Rohdaten des Laufs: <a href="run.json">run.json</a>.',
        "</footer>",
        "</main></body></html>",
    ]
    return "\n".join(p for p in parts if p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path, help="Ausgabeverzeichnis mit run.json")
    parser.add_argument("--out", type=Path, help="Zieldatei (Vorgabe: <dir>/index.html)")
    args = parser.parse_args()

    manifest = args.directory / "run.json"
    if not manifest.is_file():
        raise SystemExit(
            f"{manifest} fehlt -- zuerst 'python -m seetemp --out {args.directory}' laufen lassen."
        )
    run = json.loads(manifest.read_text(encoding="utf-8"))
    target = args.out or args.directory / "index.html"
    target.write_text(render(args.directory, run), encoding="utf-8")
    print(f"{target} geschrieben ({target.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
