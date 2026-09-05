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
# Der dritte Eintrag ist die Dateivorlage: {year} und {month_file} werden
# eingesetzt, ebenso {month_name} in Titel und Bildunterschrift.
OVERVIEW = [
    ("00_aktuell", "Heute", "00_aktuell.png",
     "Gemessener Wert je See gegenüber seinem Normalwert."),
    ("01_uebersicht_abweichung", "Alle Seen im Vergleich", "01_uebersicht_abweichung_{year}.png",
     "Mittlere Abweichung der Badesaison vom langjährigen Normalwert."),
    ("02_monatsmatrix", "Monat für Monat", "02_monatsmatrix_{year}.png",
     "Wo im Jahr die Abweichung entstanden ist -- je See und Monat."),
    ("03_badetage", "Badetage", "03_badetage_{year}.png",
     "Wie viele Tage warm genug waren, gemessen am langjährigen Mittel."),
    ("04_saisonabweichung_zeitreihe", "Jeder Sommer seit Reihenbeginn",
     "04_saisonabweichung_zeitreihe.png",
     "Ein Balken je Jahr und See -- der lange Blick auf die Entwicklung."),
    ("05_monat_je_jahr", "Jeder {month_name} der Aufzeichnung",
     "05_{month_file}_je_jahr.png",
     "Das {month_name}-Mittel jedes Jahres gegen den Normalwert desselben Monats."),
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
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; margin: 4px 0 8px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--ink-3); font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tbody tr:last-child td { border-bottom: none; }
.warm { color: #b3312f; } .cool { color: #1f5fa8; }
tr.thin td { color: var(--ink-3); }
tr.thin td:first-child::after { content: " *"; color: var(--warn-line); }
@media (prefers-color-scheme: dark) { .warm { color: #ef8b8b; } .cool { color: #6aa6ef; } }
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


def collect(root: Path, run: dict) -> tuple[list, list, list]:
    year = run.get("year", "")
    felder = {
        "year": year,
        "month_file": run.get("month_file", ""),
        "month_name": run.get("month_name", ""),
    }
    overview = []
    for _prefix, title, template, caption in OVERVIEW:
        stem = template.format(**felder)
        light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
        if light or dark:
            overview.append((title.format(**felder), caption.format(**felder), light, dark))

    lakes, heuer = [], []
    for lake in run.get("lakes", []):
        stem = f"seen/{lake['key']}_{year}.png"
        light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
        if light or dark:
            lakes.append((lake["name"], light, dark))
        stem = f"seen/{lake['key']}_heuer.png"
        light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
        if light or dark:
            heuer.append((lake["name"], light, dark))
    return overview, lakes, heuer


def current_table(run: dict) -> str:
    """Die aktuellen Werte auch als Tabelle -- Zahlen zum Nachlesen."""
    rows = run.get("current") or []
    if not rows:
        return ""
    esc = lambda v: html.escape(str(v))
    komma = lambda v: f"{v:.1f}".replace(".", ",")
    body = []
    for row in rows:
        deviation = row.get("anomaly_k")
        if deviation is None:
            cell = '<td class="n">–</td>'
        else:
            css = "warm" if deviation >= 0 else "cool"
            sign = f"{deviation:+.1f}".replace("-", "\u2212").replace(".", ",")
            cell = f'<td class="n {css}">{sign} K</td>'
        latest = row.get("temp_latest")
        jetzt = f'<td class="n">{komma(latest)} °C</td>' if latest is not None \
            else '<td class="n">–</td>'
        body.append(f"<tr><td>{esc(row['name'])}</td>{jetzt}"
                    f'<td class="n">{komma(row["temp_c"])} °C</td>{cell}</tr>')
    quelle = run.get("current_source", "")
    caveat = run.get("current_caveat", "")
    stamp = rows[0].get("latest_at") or rows[0].get("date", "")
    hinweis = f" · {esc(caveat)}" if caveat else ""
    return (
        '<table><thead><tr><th>See</th><th class="n">jetzt</th>'
        '<th class="n">Ø 24 h</th><th class="n">gegen Normalwert</th></tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
        f'<p class="caption">Stand {esc(stamp)} · {esc(quelle)}{hinweis}</p>'
    )


def coverage_table(run: dict) -> str:
    """Auf wie vielen Jahren der Normalwert je See steht.

    Ein Mittel aus zwölf Jahren ist kein Mittel aus dreissig. Wer die
    Abweichungen liest, soll sehen, wie tragfähig der Vergleichswert ist.
    """
    lakes = [l for l in run.get("lakes", []) if l.get("normal_jahre")]
    if not lakes:
        return ""
    esc = lambda v: html.escape(str(v))
    duenn = set(run.get("normal_duenn") or [])
    body = []
    for lake in sorted(lakes, key=lambda l: -l["normal_jahre"]):
        css = ' class="thin"' if lake["key"] in duenn else ""
        zeitraum = (lake.get("normal_belegung") or "").split("(")[-1].rstrip(")")
        body.append(f"<tr{css}><td>{esc(lake['name'])}</td>"
                    f'<td class="n">{lake["normal_jahre"]}</td>'
                    f"<td>{esc(zeitraum)}</td></tr>")
    hinweis = ""
    if duenn:
        hinweis = ('<p class="caption">Hervorgehoben: weniger als 20 Jahre. '
                   "Die Abweichung dieser Seen ist mit mehr Vorsicht zu lesen — "
                   "nicht falsch, aber schmaler begründet.</p>")
    return (
        '<h2>Grundlage der Normalwerte</h2>'
        '<p class="caption">Wie viele Jahre zum Vergleichswert je See beitragen. '
        "Die WMO-Normalperiode umfasst dreissig.</p>"
        '<table><thead><tr><th>See</th><th class="n">Jahre</th>'
        "<th>Zeitraum</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>{hinweis}"
    )


def render(root: Path, run: dict) -> str:
    esc = lambda v: html.escape(str(v))
    overview, lakes, heuer = collect(root, run)
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
        if title == "Heute":
            parts.append(current_table(run))

    if heuer:
        jahr = run.get("current_year") or ""
        parts += [f'<h2 class="lakes">{esc(jahr)} in Tageswerten</h2>',
                  '<p class="caption">Die amtliche lange Reihe endet mit dem letzten '
                  "Jahrbuch. Was heuer gemessen wurde, steht hier — Tag für Tag gegen "
                  "den Monatsnormalwert. Die Reihe wächst mit jedem abgelegten Abruf.</p>"]
        for name, light, dark in heuer:
            parts += [f'<p class="caption" style="margin-top:14px">{esc(name)}</p>',
                      picture(light, dark, name)]

    if lakes:
        parts += ['<h2 class="lakes">Jahresgang je See</h2>',
                  '<p class="caption">Der Verlauf des Jahres gegen den Normalwert, '
                  'das Band zeigt die Bandbreite des Bezugszeitraums.</p>']
        for name, light, dark in lakes:
            parts += [f'<p class="caption" style="margin-top:14px">{esc(name)}</p>',
                      picture(light, dark, name)]

    parts.append(coverage_table(run))
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
