"""Baut aus einem Ausgabeverzeichnis eine Übersichtsseite für den Browser.

Die Seite ist für das Handy gedacht. Ganz oben steht die Antwort auf die
Frage, mit der man sie aufruft -- wie warm ist es jetzt? -- als Karte je
See: jüngster Wert, Einordnung, Abstand zum Normalwert, Trend seit gestern,
der Verlauf der letzten Stunden als kleine Linie. Darunter die Bilder, nach
Abschnitten, je See zum Aufklappen.

Ohne JavaScript bleibt alles lesbar: Karten, Bilder, Tabellen sind fertig
im HTML. Mit JavaScript kommt dazu, was ein Bild nicht kann -- Seen suchen
und sortieren, Favoriten merken, den Verlauf antippen und den Wert unter
dem Finger sehen, das Farbschema umschalten. Bibliotheken braucht es keine;
die Seite lädt auch aus einer Datei am Handy.

Aufruf::

    python tools/build_gallery.py output/          # schreibt output/index.html
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime
from pathlib import Path

# Reihenfolge und Beschriftung der Übersichtsgrafiken, in drei Abschnitten:
# zuerst das aktuelle Geschehen, dann der Blick über die Jahre, zuletzt die
# amtliche lange Reihe -- die endet mit dem letzten Jahrbuch und ist deshalb
# das Nachschlagewerk, nicht die Titelseite.
#
# Der dritte Eintrag ist die Dateivorlage: {year}, {month_file} und {hours}
# werden eingesetzt, ebenso {month_name} in Titel und Bildunterschrift.
JETZT = [
    ("00_verlauf", "Alles, was gemessen wurde", "00_verlauf.png",
     "Jeder Tag, den wir haben: das Tagesmittel je See über den ganzen "
     "Bestand, dazu -- blasser -- die Einzelmessungen der jüngsten Tage. "
     "Die Reihe wächst mit jedem abgelegten Abruf."),
    ("00_letzte_72h", "Die letzten {hours} Stunden", "00_letzte_72h.png",
     "Alle Seen in Einzelmessungen -- wo es gerade warm ist und wie der "
     "Tagesgang verläuft. Mehr als drei Tage gibt der Dienst nicht her."),
    ("00_aktuell", "Heute gegen den Normalwert", "00_aktuell.png",
     "Gemessener Wert je See gegenüber seinem Normalwert."),
]

MONATSVERGLEICH = [
    ("05_monat_je_jahr", "Jeder {month_name} der Aufzeichnung",
     "05_{month_file}_je_jahr.png",
     "Das {month_name}-Mittel jedes Jahres gegen den Normalwert desselben Monats."),
]

LANGE_REIHE = [
    ("01_uebersicht_abweichung", "Alle Seen im Vergleich", "01_uebersicht_abweichung_{year}.png",
     "Mittlere Abweichung der Badesaison vom langjährigen Normalwert."),
    ("02_monatsmatrix", "Monat für Monat", "02_monatsmatrix_{year}.png",
     "Wo im Jahr die Abweichung entstanden ist -- je See und Monat."),
    ("03_badetage", "Badetage", "03_badetage_{year}.png",
     "Wie viele Tage warm genug waren, gemessen am langjährigen Mittel."),
    ("04_saisonabweichung_zeitreihe", "Jeder Sommer seit Reihenbeginn",
     "04_saisonabweichung_zeitreihe.png",
     "Ein Balken je Jahr und See -- der lange Blick auf die Entwicklung."),
]

#: Unter der Badeschwelle noch "frisch", darunter "kalt" -- eine grobe
#: Einordnung für den Blick aufs Handy, keine Norm. Die Schwelle selbst
#: kommt aus dem Lauf (``threshold_c``, Vorgabe 22 °C).
FRISCH_UNTER_SCHWELLE_K = 4.0

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MINUS = "−"


def num(value: float, digits: int = 1, signed: bool = False) -> str:
    """Zahl in österreichischer Schreibweise: Dezimalkomma, echtes Minus."""
    text = f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"
    if signed and abs(value) < 0.5 * 10**-digits:
        text = "±" + text.lstrip("+-")  # kein "-0,0"
    return text.replace("-", MINUS).replace(".", ",")


STYLE = """
:root {
  color-scheme: light dark;
  --bg: #fcfcfb; --card: #ffffff; --panel: #f4f3ef; --line: #e6e5e1;
  --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a8983;
  --accent: #2a78d6; --accent-ink: #ffffff;
  --warn-bg: #fdf3e7; --warn-line: #eda100; --warn-ink: #6b4a05;
  --warm: #b3312f; --cool: #1f5fa8;
  --ramp-0: #5b8fd0; --ramp-1: #1f5fa8; --ramp-2: #0b2b50;
  --b-warm-bg: #fbe3dc; --b-warm-ink: #8a2c1f;
  --b-frisch-bg: #dfeafa; --b-frisch-ink: #1d4f8c;
  --b-kalt-bg: #e9e8e3; --b-kalt-ink: #4d4c48;
  --shadow: 0 1px 2px rgba(0,0,0,.05), 0 6px 18px rgba(0,0,0,.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #1a1a19; --card: #242422; --panel: #2c2c29; --line: #333330;
    --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8f8e85;
    --accent: #3987e5; --accent-ink: #ffffff;
    --warn-bg: #2e2716; --warn-line: #c98500; --warn-ink: #f0d9a8;
    --warm: #ef8b8b; --cool: #6aa6ef;
    --ramp-0: #3987e5; --ramp-1: #77b3f2; --ramp-2: #b9dbff;
    --b-warm-bg: #4a2420; --b-warm-ink: #f5b8ad;
    --b-frisch-bg: #1f3350; --b-frisch-ink: #a9cbf5;
    --b-kalt-bg: #33332f; --b-kalt-ink: #c3c2b7;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #1a1a19; --card: #242422; --panel: #2c2c29; --line: #333330;
  --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8f8e85;
  --accent: #3987e5; --accent-ink: #ffffff;
  --warn-bg: #2e2716; --warn-line: #c98500; --warn-ink: #f0d9a8;
  --warm: #ef8b8b; --cool: #6aa6ef;
  --ramp-0: #3987e5; --ramp-1: #77b3f2; --ramp-2: #b9dbff;
  --b-warm-bg: #4a2420; --b-warm-ink: #f5b8ad;
  --b-frisch-bg: #1f3350; --b-frisch-ink: #a9cbf5;
  --b-kalt-bg: #33332f; --b-kalt-ink: #c3c2b7;
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.25);
}
:root[data-theme="light"] { color-scheme: light; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body {
  margin: 0; padding: 0 0 64px;
  background: var(--bg); color: var(--ink);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-text-size-adjust: 100%;
}
main { max-width: 900px; margin: 0 auto; padding: 0 16px; }
[id] { scroll-margin-top: 64px; }
h1 { margin: 0 0 6px; font-size: 1.55rem; line-height: 1.2; letter-spacing: -0.01em; }
h2 { margin: 0 0 2px; font-size: 1.2rem; letter-spacing: -0.005em; }
h3 { margin: 22px 0 2px; font-size: 1rem; }
section { margin-top: 44px; }
p { margin: 0 0 4px; }
.lede { color: var(--ink-2); }
.caption { color: var(--ink-3); font-size: 0.9rem; margin-bottom: 10px; }
a { color: var(--accent); }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.92em; }
button { font: inherit; color: inherit; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
/* Was nur mit JavaScript Sinn hat, bleibt ohne unsichtbar -- mit Nachdruck,
   weil spätere Regeln (.controls, .chart) sonst das display zurückholen. */
html:not(.js) .js-only { display: none !important; }
html.js .no-js { display: none; }

/* Kopfleiste: bleibt oben, führt zu den Abschnitten */
.topbar {
  position: sticky; top: 0; z-index: 20;
  background: color-mix(in srgb, var(--bg) 86%, transparent);
  -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}
@supports not (background: color-mix(in srgb, red 50%, blue)) { .topbar { background: var(--bg); } }
.topbar .inner { max-width: 900px; margin: 0 auto; padding: 0 16px; display: flex; align-items: center; gap: 8px; height: 48px; }
.brand { font-weight: 700; color: var(--ink); text-decoration: none; white-space: nowrap; letter-spacing: -0.01em; }
.tabs { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; flex: 1; -webkit-overflow-scrolling: touch; margin-left: 6px; padding-right: 24px;
  -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); }
.tabs::-webkit-scrollbar { display: none; }
.tabs a {
  color: var(--ink-2); text-decoration: none; font-size: 0.9rem; padding: 6px 10px;
  border-radius: 999px; white-space: nowrap;
}
.tabs a:hover { color: var(--ink); background: var(--panel); }
.tabs a[aria-current="true"] { color: var(--accent-ink); background: var(--accent); }
.theme {
  margin-left: auto; border: 1px solid var(--line); background: var(--card); border-radius: 999px;
  padding: 5px 10px; font-size: 0.85rem; cursor: pointer; white-space: nowrap;
}
header.intro { padding: 26px 0 4px; }

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
footer {
  margin-top: 48px; padding-top: 18px; border-top: 1px solid var(--line);
  color: var(--ink-3); font-size: 0.85rem;
}
.hint { color: var(--ink-3); font-size: 0.85rem; margin: 14px 0 0; }
ul.notes { margin: 6px 0 0; padding-left: 20px; color: var(--ink-3); font-size: 0.85rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; margin: 4px 0 8px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--ink-3); font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tbody tr:last-child td { border-bottom: none; }
.warm { color: var(--warm); } .cool { color: var(--cool); }
tr.thin td { color: var(--ink-3); }
tr.thin td:first-child::after { content: " *"; color: var(--warn-line); }

/* Aufklappbares */
details { border: 1px solid var(--line); border-radius: 12px; background: var(--card); margin: 10px 0; }
details > summary {
  cursor: pointer; padding: 12px 14px; font-weight: 600; list-style: none;
  display: flex; align-items: center; gap: 10px;
}
details > summary::-webkit-details-marker { display: none; }
details > summary::before {
  content: ""; width: 8px; height: 8px; flex: none;
  border-right: 2px solid var(--ink-3); border-bottom: 2px solid var(--ink-3);
  transform: rotate(-45deg); transition: transform .15s; margin-left: 2px;
}
details[open] > summary::before { transform: rotate(45deg); }
details > summary .sum-val { margin-left: auto; font-weight: 500; color: var(--ink-2); font-variant-numeric: tabular-nums; }
details > summary .sum-val .warm, details > summary .sum-val .cool { font-size: 0.85em; margin-left: 6px; }
details > .body { padding: 0 14px 14px; }
details > .body > figure:first-child, details > .body > h3:first-child { margin-top: 4px; }
details.lake img { border: none; border-radius: 8px; }

/* Stand und Alter */
.stand { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; color: var(--ink-3); font-size: 0.9rem; margin-bottom: 12px; }
.stand .alter { font-weight: 600; color: var(--ink-2); }
.stand .alter.stale { color: var(--warn-ink); background: var(--warn-bg); border: 1px solid var(--warn-line); border-radius: 6px; padding: 1px 8px; }

/* Kennzahlen */
.stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 12px 0 16px; }
@media (min-width: 640px) { .stats { grid-template-columns: repeat(4, 1fr); } }
.stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; min-width: 0; }
.stat .k { display: block; color: var(--ink-3); font-size: 0.75rem; text-transform: uppercase; letter-spacing: .04em; }
.stat .v { display: block; font-size: 1.1rem; font-weight: 700; line-height: 1.2; margin: 3px 0 2px; overflow-wrap: anywhere; }
.stat .s { display: block; color: var(--ink-2); font-size: 0.85rem; }

/* Suchen, sortieren, Favoriten */
.controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 0 0 12px; }
.controls .search { flex: 1 1 160px; }
.controls input[type="search"] {
  width: 100%; font: inherit; padding: 8px 12px; border-radius: 999px;
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
}
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; background: var(--card); padding: 2px; }
.seg button {
  border: 0; background: transparent; padding: 5px 11px; border-radius: 999px; cursor: pointer;
  font-size: 0.85rem; color: var(--ink-2); white-space: nowrap;
}
.seg button[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); }
.toggle {
  border: 1px solid var(--line); background: var(--card); border-radius: 999px;
  padding: 6px 12px; font-size: 0.85rem; cursor: pointer; color: var(--ink-2); white-space: nowrap;
}
.toggle[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }

/* Karten */
.cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(158px, 1fr)); }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 12px 10px;
  box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 6px; min-width: 0;
}
.card.is-fav { border-color: var(--accent); }
.card[hidden] { display: none; }
.card-top { display: flex; align-items: flex-start; gap: 6px; }
.card h3 { margin: 0; font-size: 0.95rem; line-height: 1.25; flex: 1; }
.fav {
  border: 0; background: transparent; cursor: pointer; padding: 0 2px; line-height: 1;
  font-size: 1.15rem; color: var(--ink-3); margin: -2px -4px 0 0;
}
.fav[aria-pressed="true"] { color: var(--warn-line); }
.card-now { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.big { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.05; font-variant-numeric: tabular-nums; }
.big .unit { font-size: 0.95rem; font-weight: 500; color: var(--ink-2); margin-left: 1px; }
.badge { font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: .03em; }
.b-warm { background: var(--b-warm-bg); color: var(--b-warm-ink); }
.b-frisch { background: var(--b-frisch-bg); color: var(--b-frisch-ink); }
.b-kalt { background: var(--b-kalt-bg); color: var(--b-kalt-ink); }
.spark-link { display: block; text-decoration: none; }
.spark { width: 100%; height: 40px; display: block; overflow: visible; }
.spark path { fill: none; stroke: var(--ramp-1); stroke-width: 1.8; stroke-linejoin: round; stroke-linecap: round; }
.spark .area { fill: var(--ramp-1); opacity: .10; stroke: none; }
.spark circle { fill: var(--ramp-1); stroke: var(--card); stroke-width: 1.5; }
.spark-leer { height: 40px; color: var(--ink-3); font-size: 0.78rem; display: flex; align-items: center; }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 8px; margin: 2px 0 0; }
.facts div { min-width: 0; }
.facts dt { color: var(--ink-3); font-size: 0.74rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.facts dd { margin: 0; font-size: 0.9rem; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.facts dd.up::before { content: "\\2197\\00a0"; } .facts dd.down::before { content: "\\2198\\00a0"; } .facts dd.flat::before { content: "\\2192\\00a0"; }
.facts dd.demo { color: var(--ink-3); }
.card .more { font-size: 0.85rem; margin-top: 2px; text-decoration: none; }
.card .more:hover { text-decoration: underline; }
.legende { color: var(--ink-3); font-size: 0.82rem; margin: 10px 0 0; }
.legende .badge { vertical-align: 1px; margin-right: 2px; }

/* Verlauf: das Diagramm */
.chart { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 12px 8px; margin: 10px 0; }
.chart-bar { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin-bottom: 8px; }
.chart-note { color: var(--ink-3); font-size: 0.82rem; }
.chart-box { position: relative; }
.chart-box svg { width: 100%; display: block; touch-action: pan-y; font-size: 11px; }
.chart-box svg text { fill: var(--ink-3); }
.chart-box svg .grid line { stroke: var(--line); stroke-width: 1; }
.chart-box svg .nacht { fill: var(--panel); }
.chart-box svg .linie { fill: none; stroke-width: 1.8; stroke-linejoin: round; stroke-linecap: round; }
.chart-box svg .linie.aktiv { stroke-width: 3; }
.chart-box svg .linie.blass { opacity: .22; }
.chart-box svg .ende { stroke: var(--card); stroke-width: 1.4; }
.chart-box svg .ende.blass { opacity: .22; }
.chart-box svg .normal { stroke: var(--ink-2); stroke-width: 1; stroke-dasharray: 4 4; }
.chart-box svg .normal-text { fill: var(--ink-2); font-size: 10.5px; }
.chart-box svg .name { fill: var(--ink); font-weight: 600; font-size: 12px; paint-order: stroke; stroke: var(--card); stroke-width: 4px; stroke-linejoin: round; }
.chart-box svg .cursor line { stroke: var(--ink-2); stroke-width: 1; stroke-dasharray: 3 3; }
.chart-box svg .cursor circle { fill: var(--card); stroke: var(--ink); stroke-width: 2; }
.tip {
  position: absolute; pointer-events: none; z-index: 5;
  background: var(--ink); color: var(--bg); font-size: 0.8rem; line-height: 1.35;
  padding: 6px 9px; border-radius: 8px; box-shadow: var(--shadow); white-space: nowrap;
}
.tip strong { display: block; font-size: 0.85rem; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chips button {
  border: 1px solid var(--line); background: var(--panel); color: var(--ink-2); cursor: pointer;
  border-radius: 999px; padding: 3px 9px; font-size: 0.78rem; display: inline-flex; align-items: center; gap: 6px;
}
.chips button .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.chips button[aria-pressed="true"] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.chips button .val { font-variant-numeric: tabular-nums; opacity: .8; }

/* Sprungleiste zu den Seen */
.lake-nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; }
.lake-nav a {
  text-decoration: none; color: var(--ink-2); background: var(--panel); border: 1px solid var(--line);
  border-radius: 999px; padding: 4px 10px; font-size: 0.8rem;
}
.lake-nav a:hover { color: var(--ink); }
.nach-oben {
  position: fixed; right: 14px; bottom: 14px; z-index: 15;
  border: 1px solid var(--line); background: var(--card); color: var(--ink-2);
  border-radius: 999px; width: 40px; height: 40px; cursor: pointer; box-shadow: var(--shadow);
  opacity: 0; pointer-events: none; transition: opacity .2s;
}
.nach-oben.sichtbar { opacity: 1; pointer-events: auto; }
"""


SCRIPT = r"""
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.add('js');

  // ---------------------------------------------------------- Zahlen, Zeiten
  var MINUS = '−';
  function num(v, d) {
    d = d == null ? 1 : d;
    return v.toFixed(d).replace('-', MINUS).replace('.', ',');
  }
  function signed(v, d) {
    d = d == null ? 1 : d;
    if (Math.abs(v) < 0.5 * Math.pow(10, -d)) return '±' + num(Math.abs(v), d);
    return (v > 0 ? '+' : '') + num(v, d);
  }
  var WOCHENTAGE = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  // Die Stempel sind Kärntner Wanduhrzeit ohne Zone. Als UTC gelesen und
  // als UTC ausgegeben bleibt die Uhrzeit die Kärntner, wo immer der
  // Browser steht -- Sommerzeitwechsel im Browser können sie nicht verschieben.
  function wand(text) {
    var m = /^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d))?/.exec(text || '');
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0));
  }
  function fmtTag(ms) {
    var d = new Date(ms);
    return WOCHENTAGE[d.getUTCDay()] + ' ' + d.getUTCDate() + '.' + (d.getUTCMonth() + 1) + '.';
  }
  function fmtZeit(ms) {
    var d = new Date(ms);
    return pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes());
  }
  function tausender(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
  function fold(text) {
    return String(text).toLowerCase()
      .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss');
  }

  // Der Speicher darf fehlen (privates Fenster, gesperrte Seitendaten):
  // dann merkt sich die Seite nichts, funktioniert aber.
  function lies(key, fallback) {
    try { var v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function merk(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* egal */ }
  }
  function $(sel, el) { return (el || document).querySelector(sel); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  // ---------------------------------------------------------- Farbschema
  var THEMES = ['auto', 'light', 'dark'];
  var THEME_LABEL = { auto: '◐ Auto', light: '☀ Hell', dark: '☾ Dunkel' };
  var themeButton = $('#theme');
  var hoerer = [];   // wer beim Wechsel neu zeichnen will
  function applyTheme(theme) {
    if (theme === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);
    // Die Bilder wählen ihre Fassung über <source media>; ein Schalter muss
    // das mit umstellen, sonst steht ein helles Bild auf dunklem Grund.
    var media = theme === 'dark' ? 'all' : theme === 'light' ? 'not all' : '(prefers-color-scheme: dark)';
    $$('picture > source').forEach(function (s) { s.setAttribute('media', media); });
    if (themeButton) {
      themeButton.textContent = THEME_LABEL[theme];
      themeButton.setAttribute('aria-label', 'Farbschema: ' + THEME_LABEL[theme].slice(2) + ' (antippen wechselt)');
    }
    hoerer.forEach(function (f) { f(); });
  }
  var theme = lies('seetemp.farbschema', 'auto');
  if (THEMES.indexOf(theme) < 0) theme = 'auto';
  applyTheme(theme);
  if (themeButton) {
    themeButton.addEventListener('click', function () {
      theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
      merk('seetemp.farbschema', theme);
      applyTheme(theme);
    });
  }
  if (window.matchMedia) {
    try {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if (theme === 'auto') hoerer.forEach(function (f) { f(); });
      });
    } catch (e) { /* alte Browser */ }
  }

  // ---------------------------------------------------------- Die Daten
  var daten = null;
  var datenEl = $('#aktuell-daten');
  if (datenEl) {
    try { daten = JSON.parse(datenEl.textContent); } catch (e) { daten = null; }
  }

  // ---------------------------------------------------------- Alter des Abrufs
  // Der Server schreibt "Stand 18.09., 15:00"; das ist ehrlich, aber der
  // Leser rechnet. Hier rechnet der Browser: "vor 3 Stunden" -- und ab
  // anderthalb Tagen wird daraus eine Warnung, nicht nur eine Zahl.
  var alterEl = $('#alter');
  function zeigeAlter() {
    if (!alterEl || !daten || !daten.stand) return;
    var dann = Date.parse(daten.stand);
    if (isNaN(dann)) return;
    var h = (Date.now() - dann) / 36e5;
    var text, stale = false;
    if (h < -1) { text = ''; }
    else if (h < 1) { text = 'vor wenigen Minuten'; }
    else if (h < 36) { text = 'vor ' + Math.round(h) + ' Stunden'; }
    else { text = 'vor ' + Math.round(h / 24) + ' Tagen'; stale = true; }
    if (stale) text += ' — der jüngste abgelegte Abruf ist nicht von heute';
    alterEl.textContent = text;
    alterEl.classList.toggle('stale', stale);
  }
  zeigeAlter();
  setInterval(zeigeAlter, 60000);

  // ---------------------------------------------------------- Karten
  var liste = $('#karten');
  if (liste) {
    var karten = $$('.card', liste);
    var suche = $('#suche');
    var sortKnoepfe = $$('#sortierung button');
    var favFilter = $('#nur-favoriten');
    var leer = $('#leer');
    var favoriten = lies('seetemp.favoriten', []);
    if (!Array.isArray(favoriten)) favoriten = [];
    var sortierung = lies('seetemp.sortierung', 'jetzt');
    var nurFavoriten = false;

    function istFav(key) { return favoriten.indexOf(key) >= 0; }
    function wert(card, attr) {
      var v = parseFloat(card.getAttribute(attr));
      return isNaN(v) ? null : v;
    }
    function ordne() {
      var q = suche ? fold(suche.value.trim()) : '';
      var sichtbar = 0;
      karten.sort(function (a, b) {
        var fa = istFav(a.dataset.key), fb = istFav(b.dataset.key);
        if (fa !== fb) return fa ? -1 : 1;
        if (sortierung === 'name') return a.dataset.name.localeCompare(b.dataset.name, 'de');
        var attr = sortierung === 'abw' ? 'data-abw' : 'data-jetzt';
        var va = wert(a, attr), vb = wert(b, attr);
        if (va === null && vb === null) return a.dataset.name.localeCompare(b.dataset.name, 'de');
        if (va === null) return 1;
        if (vb === null) return -1;
        return vb - va;
      });
      karten.forEach(function (card) {
        var passt = (!q || fold(card.dataset.name).indexOf(q) >= 0)
          && (!nurFavoriten || istFav(card.dataset.key));
        card.hidden = !passt;
        if (passt) sichtbar++;
        card.classList.toggle('is-fav', istFav(card.dataset.key));
        var stern = $('.fav', card);
        if (stern) {
          stern.setAttribute('aria-pressed', istFav(card.dataset.key) ? 'true' : 'false');
          stern.textContent = istFav(card.dataset.key) ? '★' : '☆';
        }
        liste.appendChild(card);
      });
      if (leer) {
        leer.hidden = sichtbar > 0;
        leer.textContent = nurFavoriten && !favoriten.length
          ? 'Noch keine Favoriten. Den Stern an einer Karte antippen, dann steht der See hier -- und immer ganz oben.'
          : 'Kein See passt zur Suche.';
      }
      sortKnoepfe.forEach(function (b) {
        b.setAttribute('aria-pressed', b.dataset.sort === sortierung ? 'true' : 'false');
      });
    }
    karten.forEach(function (card) {
      var stern = $('.fav', card);
      if (!stern) return;
      stern.addEventListener('click', function () {
        var key = card.dataset.key, i = favoriten.indexOf(key);
        if (i >= 0) favoriten.splice(i, 1); else favoriten.push(key);
        merk('seetemp.favoriten', favoriten);
        ordne();
      });
    });
    if (suche) suche.addEventListener('input', ordne);
    sortKnoepfe.forEach(function (b) {
      b.addEventListener('click', function () {
        sortierung = b.dataset.sort;
        merk('seetemp.sortierung', sortierung);
        ordne();
      });
    });
    if (favFilter) {
      favFilter.addEventListener('click', function () {
        nurFavoriten = !nurFavoriten;
        favFilter.setAttribute('aria-pressed', nurFavoriten ? 'true' : 'false');
        ordne();
      });
    }
    ordne();
  }

  // ---------------------------------------------------------- Das Diagramm
  var chart = $('#chart');
  var waehle = null;   // von aussen: einen See hervorheben
  if (chart && daten && daten.seen && daten.seen.length) {
    var svg = $('svg', chart), tip = $('.tip', chart), chips = $('#chips'), note = $('#chart-note');
    var rangeKnoepfe = $$('#bereich button');
    var bereich = daten.t0 ? '72h' : 'alles';
    var gewaehlt = null;
    var serien = [], layout = null;
    var t0 = daten.t0 ? wand(daten.t0) : null;
    // Ab dieser Lücke reisst die Linie ab statt durchzulaufen -- dieselben
    // Grenzen wie in den Bildern: drei Stunden Stille sind ein fehlender
    // Abruf, zwei fehlende Tage ein Loch in der Reihe.
    var LUECKE = { '72h': 3 * 36e5, 'alles': 2 * 864e5 };

    function cssVar(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }
    function hex(c) {
      var m = /^#?([0-9a-f]{6})$/i.exec(c);
      if (!m) return [0, 0, 0];
      var n = parseInt(m[1], 16);
      return [n >> 16 & 255, n >> 8 & 255, n & 255];
    }
    function mix(a, b, t) {
      return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * t); }).join(',') + ')';
    }
    // Die Farbe folgt allein der Temperatur -- fünfzehn Seen vertragen
    // keine fünfzehn Farben. Wer welcher ist, sagen Chip und Fingertipp.
    function ramp(n) {
      var c0 = hex(cssVar('--ramp-0')), c1 = hex(cssVar('--ramp-1')), c2 = hex(cssVar('--ramp-2'));
      var out = [];
      for (var i = 0; i < n; i++) {
        var t = n <= 1 ? 1 : i / (n - 1);
        out.push(t < 0.5 ? mix(c0, c1, t * 2) : mix(c1, c2, (t - 0.5) * 2));
      }
      return out;
    }

    function reihen() {
      var out = [];
      daten.seen.forEach(function (s) {
        var pts;
        if (bereich === '72h') {
          if (t0 === null) return;
          pts = s.punkte.map(function (p) { return { t: t0 + p[0] * 60000, v: p[1] }; });
        } else {
          pts = s.tage.map(function (d) { return { t: wand(d[0]), v: d[1], n: d[2] }; });
        }
        if (!pts.length) return;
        out.push({ key: s.key, name: s.name, pts: pts, letzte: pts[pts.length - 1].v, normal: s.normal });
      });
      // Farbe nach Rang der jüngsten Temperatur.
      var ordnung = out.slice().sort(function (a, b) { return a.letzte - b.letzte; });
      var farben = ramp(ordnung.length);
      ordnung.forEach(function (s, i) { s.farbe = farben[i]; });
      return out;
    }

    function nice(step) {
      var p = Math.pow(10, Math.floor(Math.log10(step)));
      var f = step / p;
      return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
    }

    function zeichne() {
      serien = reihen();
      if (!serien.length) { svg.innerHTML = ''; return; }
      var W = chart.clientWidth - 24 || 320;
      var H = Math.max(240, Math.min(400, Math.round(W * 0.58)));
      var m = { l: 34, r: 16, t: 14, b: 30 };
      var tMin = Infinity, tMax = -Infinity, vMin = Infinity, vMax = -Infinity;
      serien.forEach(function (s) {
        s.pts.forEach(function (p) {
          if (p.t < tMin) tMin = p.t; if (p.t > tMax) tMax = p.t;
          if (p.v < vMin) vMin = p.v; if (p.v > vMax) vMax = p.v;
        });
      });
      var luft = Math.max(0.6, (vMax - vMin) * 0.06);
      vMin -= luft; vMax += luft;
      var tPad = (tMax - tMin) * 0.02 || 36e5;
      var x = function (t) { return m.l + (t - tMin) / (tMax + tPad - tMin) * (W - m.l - m.r); };
      var y = function (v) { return m.t + (vMax - v) / (vMax - vMin) * (H - m.t - m.b); };
      layout = { W: W, H: H, m: m, x: x, y: y, tMin: tMin, tMax: tMax };

      var out = [];
      // Nacht als blasses Feld, wie im Bild: der Tagesgang erklärt sich damit selbst.
      if (bereich === '72h') {
        var tag = Math.floor(tMin / 864e5) * 864e5 - 864e5;
        while (tag <= tMax) {
          var von = Math.max(tag + 20 * 36e5, tMin), bis = Math.min(tag + 30 * 36e5, tMax);
          if (von < bis) out.push('<rect class="nacht" x="' + x(von).toFixed(1) + '" y="' + m.t + '" width="' + (x(bis) - x(von)).toFixed(1) + '" height="' + (H - m.t - m.b) + '"/>');
          tag += 864e5;
        }
      }
      // Raster und Achsen.
      var stepY = nice((vMax - vMin) / 5);
      out.push('<g class="grid">');
      for (var v = Math.ceil(vMin / stepY) * stepY; v <= vMax; v += stepY) {
        out.push('<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + y(v).toFixed(1) + '" y2="' + y(v).toFixed(1) + '"/>');
        out.push('<text x="' + (m.l - 6) + '" y="' + (y(v) + 4).toFixed(1) + '" text-anchor="end">' + num(v, stepY < 1 ? 1 : 0) + '</text>');
      }
      var ticks = [];
      if (bereich === '72h') {
        var pxPro6h = x(tMin + 6 * 36e5) - x(tMin);
        var mark = Math.ceil(tMin / (6 * 36e5)) * 6 * 36e5;
        while (mark <= tMax) {
          var h = new Date(mark).getUTCHours(), label = '';
          if (h === 0) label = fmtTag(mark);
          else if (h === 12 && pxPro6h >= 40) label = '12 Uhr';
          ticks.push({ t: mark, label: label });
          mark += 6 * 36e5;
        }
      } else {
        var tage = Math.round((tMax - tMin) / 864e5) + 1;
        var pxProTag = (W - m.l - m.r) / Math.max(tage, 1);
        var jeder = Math.max(1, Math.ceil(56 / pxProTag));
        var d0 = Math.floor(tMin / 864e5) * 864e5;
        for (var i = 0; d0 + i * 864e5 <= tMax; i++) {
          var tt = d0 + i * 864e5;
          ticks.push({ t: tt, label: i % jeder === 0 ? fmtTag(tt) : '' });
        }
      }
      ticks.forEach(function (tk) {
        var xx = x(tk.t).toFixed(1);
        out.push('<line x1="' + xx + '" x2="' + xx + '" y1="' + m.t + '" y2="' + (H - m.b) + '"/>');
        if (tk.label) out.push('<text x="' + xx + '" y="' + (H - m.b + 16) + '" text-anchor="middle">' + tk.label + '</text>');
      });
      out.push('</g>');

      // Normalwert des hervorgehobenen Sees: gestrichelt, damit der Blick
      // "wärmer als üblich?" nicht erst zur Tabelle muss.
      var aktiv = null;
      serien.forEach(function (s) { if (s.key === gewaehlt) aktiv = s; });
      if (aktiv && aktiv.normal != null && aktiv.normal > vMin && aktiv.normal < vMax) {
        var yn = y(aktiv.normal).toFixed(1);
        out.push('<line class="normal" x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + yn + '" y2="' + yn + '"/>');
        out.push('<text class="normal-text" x="' + (m.l + 4) + '" y="' + (y(aktiv.normal) - 4).toFixed(1) + '">Normalwert ' + num(aktiv.normal) + ' °C' + (daten.normal_demo ? ' (Demo)' : '') + '</text>');
      }

      // Die Linien: der gewählte See kräftig und zuletzt, die anderen blass.
      var luecke = LUECKE[bereich];
      var sortiert = serien.slice().sort(function (a, b) { return (a.key === gewaehlt) - (b.key === gewaehlt); });
      sortiert.forEach(function (s) {
        var d = '', vorher = null;
        s.pts.forEach(function (p) {
          d += (vorher === null || p.t - vorher > luecke ? 'M' : 'L') + x(p.t).toFixed(1) + ' ' + y(p.v).toFixed(1);
          vorher = p.t;
        });
        var cls = 'linie' + (gewaehlt ? (s.key === gewaehlt ? ' aktiv' : ' blass') : '');
        out.push('<path class="' + cls + '" data-key="' + s.key + '" d="' + d + '" stroke="' + s.farbe + '"/>');
        var last = s.pts[s.pts.length - 1];
        out.push('<circle class="ende' + (gewaehlt && s.key !== gewaehlt ? ' blass' : '') + '" cx="' + x(last.t).toFixed(1) + '" cy="' + y(last.v).toFixed(1) + '" r="' + (s.key === gewaehlt ? 4.5 : 3) + '" fill="' + s.farbe + '"/>');
        if (s.key === gewaehlt) {
          var lx = x(last.t), anchor = lx > W - 110 ? 'end' : 'start';
          out.push('<text class="name" x="' + (lx + (anchor === 'end' ? -8 : 8)).toFixed(1) + '" y="' + (y(last.v) - 8).toFixed(1) + '" text-anchor="' + anchor + '">' + esc(s.name) + ' ' + num(last.v) + ' °C</text>');
        }
      });
      out.push('<g class="cursor" hidden><line/><circle r="5"/></g>');
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      svg.setAttribute('height', H);
      svg.innerHTML = out.join('');
      if (tip) tip.hidden = true;

      if (note) {
        if (bereich === '72h') {
          var n = 0; serien.forEach(function (s) { n += s.pts.length; });
          note.textContent = 'Einzelmessungen ' + fmtTag(tMin) + ' ' + fmtZeit(tMin) + ' bis ' + fmtTag(tMax) + ' ' + fmtZeit(tMax) + ' · ' + tausender(n) + ' Werte · Uhrzeit Kärnten';
        } else {
          note.textContent = 'Tagesmittel je See, ' + fmtTag(tMin) + ' bis ' + fmtTag(tMax) + ' · Lücken bleiben Lücken';
        }
      }
      zeichneChips();
    }
    function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

    function zeichneChips() {
      if (!chips) return;
      var out = ['<button type="button" data-key="" aria-pressed="' + (gewaehlt ? 'false' : 'true') + '">Alle Seen</button>'];
      serien.slice().sort(function (a, b) { return b.letzte - a.letzte; }).forEach(function (s) {
        out.push('<button type="button" data-key="' + s.key + '" aria-pressed="' + (s.key === gewaehlt ? 'true' : 'false') + '">'
          + '<span class="dot" style="background:' + s.farbe + '"></span>' + esc(s.name)
          + ' <span class="val">' + num(s.letzte) + '°</span></button>');
      });
      chips.innerHTML = out.join('');
    }
    if (chips) {
      chips.addEventListener('click', function (ev) {
        var b = ev.target.closest('button');
        if (!b) return;
        var key = b.dataset.key;
        gewaehlt = (!key || key === gewaehlt) ? null : key;
        zeichne();
      });
    }
    rangeKnoepfe.forEach(function (b) {
      b.addEventListener('click', function () {
        bereich = b.dataset.range;
        rangeKnoepfe.forEach(function (o) { o.setAttribute('aria-pressed', o === b ? 'true' : 'false'); });
        zeichne();
      });
      if (!daten.t0 && b.dataset.range === '72h') b.disabled = true;
    });

    // Fingertipp oder Mauszeiger: der nächste Punkt, sein Wert, seine Zeit.
    function zeige(ev) {
      if (!layout || !serien.length) return;
      var r = svg.getBoundingClientRect();
      var px = (ev.clientX - r.left) * layout.W / r.width;
      var py = (ev.clientY - r.top) * layout.H / r.height;
      var best = null, bestD = Infinity;
      serien.forEach(function (s) {
        if (gewaehlt && s.key !== gewaehlt) return;
        // Binäre Suche nach der Zeit, dann Abstand in Bildpunkten.
        var lo = 0, hi = s.pts.length - 1;
        while (lo < hi) {
          var mid = (lo + hi) >> 1;
          if (layout.x(s.pts[mid].t) < px) lo = mid + 1; else hi = mid;
        }
        [lo - 1, lo].forEach(function (i) {
          if (i < 0 || i >= s.pts.length) return;
          var p = s.pts[i];
          var dx = layout.x(p.t) - px, dy = layout.y(p.v) - py;
          var d = gewaehlt ? Math.abs(dx) : Math.sqrt(dx * dx + dy * dy);
          if (d < bestD) { bestD = d; best = { s: s, p: p }; }
        });
      });
      var cursor = $('.cursor', svg);
      if (!best || (!gewaehlt && bestD > 60)) {
        if (cursor) cursor.hidden = true;
        if (tip) tip.hidden = true;
        return;
      }
      var cx = layout.x(best.p.t), cy = layout.y(best.p.v);
      if (cursor) {
        cursor.hidden = false;
        var line = $('line', cursor), dot = $('circle', cursor);
        line.setAttribute('x1', cx); line.setAttribute('x2', cx);
        line.setAttribute('y1', layout.m.t); line.setAttribute('y2', layout.H - layout.m.b);
        dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
      }
      if (tip) {
        var wann = bereich === '72h' ? fmtTag(best.p.t) + ', ' + fmtZeit(best.p.t) : fmtTag(best.p.t);
        var extra = bereich === 'alles' && best.p.n ? ' · Tagesmittel aus ' + best.p.n + ' Messungen' : '';
        tip.innerHTML = '<strong>' + esc(best.s.name) + ' ' + num(best.p.v) + ' °C</strong>' + wann + extra;
        tip.hidden = false;
        var sx = cx * r.width / layout.W, sy = cy * r.height / layout.H;
        var tw = tip.offsetWidth, th = tip.offsetHeight;
        var left = sx + 12, top = sy - th - 10;
        if (left + tw > r.width) left = sx - tw - 12;
        if (left < 0) left = 4;
        if (top < 0) top = sy + 14;
        tip.style.left = left + 'px'; tip.style.top = top + 'px';
      }
    }
    svg.addEventListener('pointermove', zeige);
    svg.addEventListener('pointerdown', zeige);
    svg.addEventListener('pointerleave', function (ev) {
      if (ev.pointerType === 'mouse') {
        var cursor = $('.cursor', svg);
        if (cursor) cursor.hidden = true;
        if (tip) tip.hidden = true;
      }
    });
    var timer = null;
    window.addEventListener('resize', function () {
      clearTimeout(timer); timer = setTimeout(zeichne, 150);
    });
    hoerer.push(zeichne);
    waehle = function (key) {
      gewaehlt = key;
      if (bereich !== '72h' && daten.t0) {
        bereich = '72h';
        rangeKnoepfe.forEach(function (o) { o.setAttribute('aria-pressed', o.dataset.range === '72h' ? 'true' : 'false'); });
      }
      zeichne();
    };
    zeichne();
  } else if (chart) {
    chart.hidden = true;
  }

  // Von der Karte ins Diagramm: der See bleibt dort hervorgehoben.
  $$('a[data-lake]').forEach(function (a) {
    a.addEventListener('click', function () { if (waehle) waehle(a.dataset.lake); });
  });

  // ---------------------------------------------------------- Aufklappen
  // Ein Link in einen zugeklappten Abschnitt soll ihn öffnen -- sonst
  // springt die Seite zu einer Zeile, hinter der nichts zu sehen ist.
  function oeffne(hash) {
    if (!hash || hash.length < 2) return;
    var el = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!el) return;
    var d = el.closest('details');
    while (d) { d.open = true; d = d.parentElement && d.parentElement.closest('details'); }
  }
  $$('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function () { oeffne(a.getAttribute('href')); });
  });
  window.addEventListener('hashchange', function () { oeffne(location.hash); });
  oeffne(location.hash);
  // Mit Diagramm sind die grossen Bilder dazu eine Wiederholung: zugeklappt,
  // einen Tipp entfernt. Ohne JavaScript bleiben sie offen.
  $$('details.bilder').forEach(function (d) { if (chart && !chart.hidden) d.open = false; });

  // ---------------------------------------------------------- Kopfleiste
  var tabs = $$('.tabs a');
  if (tabs.length && 'IntersectionObserver' in window) {
    var ziele = tabs.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); }).filter(Boolean);
    var sichtbar = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { sichtbar[e.target.id] = e.isIntersecting ? e.boundingClientRect.top : null; });
      var oben = null;
      ziele.forEach(function (z) {
        if (sichtbar[z.id] != null && (oben === null || sichtbar[z.id] < sichtbar[oben.id])) oben = z;
      });
      if (!oben) return;
      tabs.forEach(function (a) {
        if (a.getAttribute('href') === '#' + oben.id) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
    }, { rootMargin: '-56px 0px -60% 0px', threshold: 0 });
    ziele.forEach(function (z) { io.observe(z); });
  }
  var hoch = $('#nach-oben');
  if (hoch) {
    var pruefe = function () { hoch.classList.toggle('sichtbar', window.scrollY > 600); };
    window.addEventListener('scroll', pruefe, { passive: true });
    hoch.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    pruefe();
  }
})();
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


def collect(root: Path, run: dict) -> dict:
    """Sucht zu jedem Abschnitt die Bilder, die tatsächlich vorliegen."""
    year = run.get("year", "")
    felder = {
        "year": year,
        "month_file": run.get("month_file", ""),
        "month_name": run.get("month_name", ""),
        "hours": (run.get("recent") or {}).get("hours", 72),
    }

    def gruppe(eintraege: list) -> list:
        gefunden = []
        for prefix, title, template, caption in eintraege:
            stem = template.format(**felder)
            light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
            if light or dark:
                gefunden.append((prefix, title.format(**felder),
                                 caption.format(**felder), light, dark))
        return gefunden

    def seen(vorlage: str) -> list:
        gefunden = []
        for lake in run.get("lakes", []):
            stem = f"seen/{vorlage.format(key=lake['key'], year=year)}"
            light, dark = find(root, f"light/{stem}"), find(root, f"dark/{stem}")
            if light or dark:
                gefunden.append((lake["key"], lake["name"], light, dark))
        return gefunden

    return {
        "jetzt": gruppe(JETZT),
        "monat": gruppe(MONATSVERGLEICH),
        "reihe": gruppe(LANGE_REIHE),
        "heuer": seen("{key}_heuer.png"),
        "lakes": seen("{key}_{year}.png"),
    }


def load_aktuell(root: Path) -> dict | None:
    """Die Zahlen für Karten und Diagramm, wenn der Lauf sie geschrieben hat."""
    path = root / "aktuell.json"
    if not path.is_file():
        return None
    try:
        daten = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return daten if isinstance(daten, dict) and daten.get("seen") else None


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
            sign = f"{deviation:+.1f}".replace("-", "−").replace(".", ",")
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
        '<details id="grundlage"><summary>Grundlage der Normalwerte</summary><div class="body">'
        '<p class="caption">Wie viele Jahre zum Vergleichswert je See beitragen. '
        "Die WMO-Normalperiode umfasst dreissig.</p>"
        '<table><thead><tr><th>See</th><th class="n">Jahre</th>'
        "<th>Zeitraum</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>{hinweis}</div></details>"
    )


# ------------------------------------------------------------- Der Abschnitt "Jetzt"

def einordnung(jetzt: float | None, schwelle: float) -> tuple[str, str]:
    """Badewarm, frisch oder kalt -- CSS-Klasse und Wort."""
    if jetzt is None:
        return "", ""
    if jetzt >= schwelle:
        return "b-warm", "badewarm"
    if jetzt >= schwelle - FRISCH_UNTER_SCHWELLE_K:
        return "b-frisch", "frisch"
    return "b-kalt", "kalt"


def sparkline(punkte: list, fenster_min: int | None = None) -> str:
    """Kleine Linie der letzten Stunden, fertig gezeichnet -- ohne JavaScript.

    Die Skala ist je See die eigene: die Linie zeigt die Form des Tagesgangs,
    nicht den Vergleich zwischen Seen. Dafür stehen die Zahlen daneben.
    """
    if len(punkte) < 2:
        return ""
    W, H, pad = 120.0, 32.0, 3.0
    xs = [p[0] for p in punkte]
    ys = [p[1] for p in punkte]
    x0, x1 = min(xs), max(xs)
    if fenster_min:
        x0 = min(x0, x1 - fenster_min)
    y0, y1 = min(ys), max(ys)
    if y1 - y0 < 0.5:  # ein fast waagrechter Verlauf soll nicht wie ein Gebirge aussehen
        mitte = (y0 + y1) / 2
        y0, y1 = mitte - 0.25, mitte + 0.25
    sx = lambda v: pad + (v - x0) / max(x1 - x0, 1) * (W - 2 * pad)
    sy = lambda v: H - pad - (v - y0) / (y1 - y0) * (H - 2 * pad)
    # Wie im grossen Bild: drei Stunden Stille sind eine Lücke, keine Linie.
    d, vorher = [], None
    for x, y in zip(xs, ys):
        d.append(("M" if vorher is None or x - vorher > 180 else "L")
                 + f"{sx(x):.1f} {sy(y):.1f}")
        vorher = x
    area = (f"M{sx(xs[0]):.1f} {H:.0f} " + " ".join(
        f"L{sx(x):.1f} {sy(y):.1f}" for x, y in zip(xs, ys)) + f" L{sx(xs[-1]):.1f} {H:.0f} Z")
    titel = f"Verlauf der letzten Stunden: {num(min(ys))} bis {num(max(ys))} °C"
    return (
        f'<svg class="spark" viewBox="0 0 {W:.0f} {H:.0f}" preserveAspectRatio="none" '
        f'role="img" aria-label="{html.escape(titel, quote=True)}">'
        f'<path class="area" d="{area}"/><path d="{" ".join(d)}"/>'
        f'<circle cx="{sx(xs[-1]):.1f}" cy="{sy(ys[-1]):.1f}" r="2.6"/></svg>'
    )


def _wann(text: str | None, kurz: bool = False) -> str:
    """'2026-09-18T15:00' -> 'Fr 18.9., 15:00' -- so, wie man es sagt.

    Kurz: 'Fr 15:00' -- für die Karte, wo das Datum schon über allem steht.
    """
    if not text:
        return "–"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return html.escape(text)
    wochentag = WOCHENTAGE[stamp.weekday()]
    tag = f"{wochentag} {stamp.day}.{stamp.month}."
    if len(text) <= 10:
        return tag
    return f"{wochentag} {stamp:%H:%M}" if kurz else f"{tag}, {stamp:%H:%M}"


def _ohne_alter(quelle: str) -> str:
    """'… abgelegter Abruf (2 h alt)' -> '… abgelegter Abruf'.

    Das Alter zur Bauzeit steht in Bild und Tabelle; über den Karten rechnet
    der Browser es live, zwei Angaben nebeneinander verwirrten nur.
    """
    return re.sub(r"\s*\((frisch|[^()]*\balt)\)\s*$", "", quelle)


def stat_tiles(seen: list, schwelle: float) -> str:
    """Vier Kennzahlen über den Karten: die Antworten auf einen Blick."""
    esc = lambda v: html.escape(str(v))
    mit_wert = [s for s in seen if s.get("jetzt") is not None]
    if not mit_wert:
        return ""
    waermster = max(mit_wert, key=lambda s: s["jetzt"])
    kaeltester = min(mit_wert, key=lambda s: s["jetzt"])
    warm = sum(1 for s in mit_wert if s["jetzt"] >= schwelle)
    mit_normal = [s for s in seen if s.get("abweichung") is not None]
    ueber = sum(1 for s in mit_normal if s["abweichung"] > 0)
    tiles = [
        ("Wärmster See", esc(waermster["name"]), f"{num(waermster['jetzt'])} °C"),
        ("Kältester See", esc(kaeltester["name"]), f"{num(kaeltester['jetzt'])} °C"),
        (f"Badewarm ab {num(schwelle, 0)} °C", f"{warm} von {len(mit_wert)}", "Seen"),
    ]
    if mit_normal:
        tiles.append(("Wärmer als normal", f"{ueber} von {len(mit_normal)}",
                      "Seen mit Normalwert"))
    return '<div class="stats">' + "".join(
        f'<div class="stat"><span class="k">{k}</span><span class="v">{v}</span>'
        f'<span class="s">{s}</span></div>' for k, v, s in tiles) + "</div>"


def lake_card(see: dict, schwelle: float, fenster_min: int, demo: bool,
              heuer_keys: set) -> str:
    esc = lambda v: html.escape(str(v))
    key, name = see["key"], see["name"]
    jetzt = see.get("jetzt")
    klasse, wort = einordnung(jetzt, schwelle)
    gross = (f'<span class="big">{num(jetzt)}<span class="unit">°C</span></span>'
             if jetzt is not None else '<span class="big">–</span>')
    badge = f'<span class="badge {klasse}">{wort}</span>' if wort else ""

    spark = sparkline(see.get("punkte") or [], fenster_min)
    if spark:
        spark = f'<a class="spark-link" href="#verlauf" data-lake="{esc(key)}">{spark}</a>'
    else:
        spark = '<div class="spark-leer">keine Einzelmessungen abgelegt</div>'

    abw = see.get("abweichung")
    if abw is None:
        abw_html = '<dd title="Für diesen See gibt es keine lange Reihe">kein Normalwert</dd>'
    else:
        css = "warm" if abw > 0 else "cool" if abw < 0 else ""
        css = (css + " demo").strip() if demo else css
        titel = ' title="Normalwert aus dem Demomodell"' if demo else ""
        titel = titel or ' title="Mittel der letzten 24 h gegenüber dem Normalwert"'
        abw_html = f'<dd class="{css}"{titel}>{num(abw, signed=True)} K</dd>'
    trend = see.get("trend_24h")
    if trend is None:
        trend_html = "<dd>–</dd>"
    else:
        richtung = "up" if trend >= 0.3 else "down" if trend <= -0.3 else "flat"
        trend_html = (f'<dd class="{richtung}" title="Mittel der letzten 24 h gegenüber '
                      f'den 24 h davor">{num(trend, signed=True)} K</dd>')
    mittel = see.get("mittel_24h")
    mittel_html = f"<dd>{num(mittel)} °C</dd>" if mittel is not None else "<dd>–</dd>"

    facts = (
        '<dl class="facts">'
        f"<div><dt>Abweichung</dt>{abw_html}</div>"
        f"<div><dt>Trend</dt>{trend_html}</div>"
        f"<div><dt>Ø 24 h</dt>{mittel_html}</div>"
        f'<div><dt>Gemessen</dt><dd title="{_wann(see.get("jetzt_um"))}">'
        f"{_wann(see.get('jetzt_um'), kurz=True)}</dd></div>"
        "</dl>"
    )
    mehr = (f'<a class="more" href="#heuer-{esc(key)}">Verlauf heuer →</a>'
            if key in heuer_keys else "")
    attrs = (f'data-key="{esc(key)}" data-name="{esc(name)}" '
             f'data-jetzt="{"" if jetzt is None else jetzt}" '
             f'data-abw="{"" if abw is None else abw}"')
    return (
        f'<li class="card" id="see-{esc(key)}" {attrs}>'
        f'<div class="card-top"><h3>{esc(name)}</h3>'
        f'<button type="button" class="fav js-only" aria-pressed="false" '
        f'aria-label="{esc(name)} als Favorit merken">☆</button></div>'
        f'<div class="card-now">{gross}{badge}</div>'
        f"{spark}{facts}{mehr}</li>"
    )


def jetzt_section(daten: dict | None, run: dict, heuer_keys: set) -> str:
    """Karten, Kennzahlen, Bedienelemente -- und die Tabelle zum Nachlesen."""
    esc = lambda v: html.escape(str(v))
    tabelle = current_table(run)
    if not daten and not tabelle:
        return ""
    parts = ['<section id="jetzt">', "<h2>Wie warm ist es jetzt?</h2>"]
    if daten:
        seen = daten.get("seen") or []
        schwelle = float(daten.get("schwelle_c") or run.get("threshold_c") or 22.0)
        fenster = int(daten.get("fenster_h") or 72) * 60
        demo = bool(daten.get("normal_demo"))
        stand = _wann(daten.get("stand_lokal"))
        quelle = _ohne_alter(daten.get("quelle") or run.get("current_source") or "")
        hinweis = daten.get("hinweis") or ""
        parts += [
            '<p class="caption">Der jüngste Messwert je See, dazu die Einordnung: '
            "wie das Tagesmittel gegen den Normalwert steht und ob es seit gestern "
            "steigt. Die kleine Linie ist der Verlauf der letzten drei Tage.</p>",
            f'<p class="stand">Stand <time datetime="{esc(daten.get("stand") or "")}">{stand}</time>'
            f' <span id="alter" class="alter"></span><span>{esc(quelle)}</span>'
            + (f"<span>{esc(hinweis)}</span>" if hinweis else "") + "</p>",
            stat_tiles(seen, schwelle),
            '<div class="controls js-only">'
            '<label class="search"><span class="sr">See suchen</span>'
            '<input type="search" id="suche" placeholder="See suchen …" autocomplete="off"></label>'
            '<div class="seg" id="sortierung" role="group" aria-label="Sortierung">'
            '<button type="button" data-sort="jetzt" aria-pressed="true">Wärmste zuerst</button>'
            '<button type="button" data-sort="name" aria-pressed="false">A–Z</button>'
            '<button type="button" data-sort="abw" aria-pressed="false">Abweichung</button></div>'
            '<button type="button" id="nur-favoriten" class="toggle" aria-pressed="false">★ Meine Seen</button>'
            "</div>",
            '<ul class="cards" id="karten">'
            + "".join(lake_card(s, schwelle, fenster, demo, heuer_keys) for s in seen)
            + "</ul>",
            '<p class="hint js-only" id="leer" hidden></p>',
            '<p class="legende"><span class="badge b-warm">badewarm</span> ab '
            f"{num(schwelle, 0)} °C · <span class=\"badge b-frisch\">frisch</span> ab "
            f"{num(schwelle - FRISCH_UNTER_SCHWELLE_K, 0)} °C · darunter "
            '<span class="badge b-kalt">kalt</span>. Abweichung: das Mittel der letzten '
            "24 Stunden gegen den Normalwert des Tages. Trend: dasselbe Mittel gegen das "
            "der 24 Stunden davor — so bleibt der Tagesgang aussen vor. "
            "Der Stern merkt einen See auf diesem Gerät als Favorit.</p>",
        ]
    if tabelle:
        offen = "" if daten else " open"
        parts.append(f'<details id="tabelle"{offen}><summary>Alle Werte als Tabelle</summary>'
                     f'<div class="body">{tabelle}</div></details>')
    parts.append("</section>")
    return "\n".join(parts)


def verlauf_section(daten: dict | None, bilder: list) -> str:
    """Das Diagramm zum Antippen, darunter die Bilder zum Speichern."""
    if not daten and not bilder:
        return ""
    parts = ['<section id="verlauf">', "<h2>Verlauf</h2>"]
    if daten:
        hat_tage = any(s.get("tage") for s in daten.get("seen") or [])
        hat_punkte = any(s.get("punkte") for s in daten.get("seen") or [])
        parts += [
            '<p class="caption">Die letzten drei Tage in Einzelmessungen'
            + (" — oder alles, was seit dem ersten Abruf abgelegt wurde, als Tagesmittel"
               if hat_tage else "")
            + ". Einen See antippen hebt ihn hervor und zeigt seinen Normalwert; "
              "über die Linien fahren oder tippen zeigt den Wert.</p>",
            '<div class="chart js-only" id="chart">',
            '<div class="chart-bar"><div class="seg" id="bereich" role="group" aria-label="Zeitraum">'
            f'<button type="button" data-range="72h" aria-pressed="{"true" if hat_punkte else "false"}">'
            f'{daten.get("fenster_h") or 72} Stunden</button>'
            f'<button type="button" data-range="alles" aria-pressed="{"false" if hat_punkte else "true"}"'
            f'{"" if hat_tage else " disabled"}>Alles</button></div>'
            '<span class="chart-note" id="chart-note"></span></div>',
            '<div class="chart-box"><svg role="img" aria-label="Wassertemperatur je See im Verlauf"></svg>'
            '<div class="tip" hidden></div></div>',
            '<div class="chips" id="chips"></div>',
            "</div>",
        ]
    if bilder:
        parts.append('<details class="bilder" open><summary>Die Bilder dazu — zum Speichern und Teilen</summary>'
                     '<div class="body">')
        for _prefix, title, caption, light, dark in bilder:
            parts += [f"<h3>{html.escape(title)}</h3>",
                      f'<p class="caption">{html.escape(caption)}</p>',
                      picture(light, dark, title)]
        parts.append("</div></details>")
    parts.append("</section>")
    return "\n".join(parts)


def lake_details(prefix: str, eintraege: list, werte: dict) -> str:
    """Je See ein Abschnitt zum Aufklappen, davor die Sprungleiste."""
    esc = lambda v: html.escape(str(v))
    nav = '<nav class="lake-nav" aria-label="Seen">' + "".join(
        f'<a href="#{prefix}-{esc(key)}">{esc(name)}</a>' for key, name, _l, _d in eintraege
    ) + "</nav>"
    parts = [nav]
    for key, name, light, dark in eintraege:
        wert = werte.get(key)
        summe = ""
        if wert and wert.get("jetzt") is not None:
            abw = wert.get("abweichung")
            zusatz = ""
            if abw is not None:
                css = "warm" if abw > 0 else "cool"
                zusatz = f'<span class="{css}">{num(abw, signed=True)} K</span>'
            summe = f'<span class="sum-val">{num(wert["jetzt"])} °C{zusatz}</span>'
        parts.append(
            f'<details class="lake" id="{prefix}-{esc(key)}"><summary>{esc(name)}{summe}</summary>'
            f'<div class="body">{picture(light, dark, name)}</div></details>'
        )
    return "\n".join(parts)


def topbar(abschnitte: list[tuple[str, str]]) -> str:
    tabs = "".join(f'<a href="#{i}">{html.escape(t)}</a>' for i, t in abschnitte)
    return (
        '<nav class="topbar" aria-label="Seitenbereiche"><div class="inner">'
        '<a class="brand" href="#top">Kärntner Seen</a>'
        f'<div class="tabs">{tabs}</div>'
        '<button type="button" class="theme js-only" id="theme">◐ Auto</button>'
        "</div></nav>"
    )


def render(root: Path, run: dict) -> str:
    esc = lambda v: html.escape(str(v))
    bilder = collect(root, run)
    daten = load_aktuell(root)
    year = run.get("year", "")
    generated = datetime.fromisoformat(run["generated_at"]).strftime("%d.%m.%Y, %H:%M UTC")
    aufloesung = "Tageswerte" if run.get("resolution") == "daily" else "Monatsmittel"
    werte = f"{run.get('values', 0):,}".replace(",", ".")
    reihe_bis = str(run.get("data_until", ""))[:4]
    heuer_keys = {key for key, _n, _l, _d in bilder["heuer"]}
    je_see = {s["key"]: s for s in (daten or {}).get("seen") or []}

    banner = ""
    if run.get("is_demo"):
        # Die Werte der letzten Stunden kommen vom Landesdienst, nicht aus dem
        # Modell. Sie mitzuverdammen wäre so falsch wie sie zu beschönigen.
        gemessen = ""
        if run.get("recent") or run.get("current"):
            gemessen = (" Die Messwerte der letzten Tage ganz oben sind davon "
                        "ausgenommen: sie sind gemessen.")
        banner = (
            '<div class="warn"><strong>Demodaten — keine langjährigen Messwerte.'
            "</strong>Die Normalwerte und der Vergleich mit ihnen beruhen auf einem "
            "synthetischen Jahresgangmodell und sagen nichts über die tatsächlichen "
            f"Seen aus.{gemessen} Für echte Werte den Lauf mit der Quelle "
            "<code>ehyd</code> starten.</div>"
        )

    skipped = "".join(
        f"<li>Übersprungen: {esc(item)}</li>" for item in run.get("skipped", [])
    )
    notes = "".join(f"<li>{esc(note)}</li>" for note in run.get("notes", [])[:6])
    notes_block = f'<ul class="notes">{skipped}{notes}</ul>' if (skipped or notes) else ""

    # Die Bilder des aktuellen Geschehens: Bestand und letzte Stunden gehören
    # zum Verlauf, "heute gegen den Normalwert" bekommt einen eigenen Abschnitt.
    verlauf_bilder = [b for b in bilder["jetzt"] if b[0] in ("00_verlauf", "00_letzte_72h")]
    normal_bilder = [b for b in bilder["jetzt"] if b[0] == "00_aktuell"]

    abschnitte: list[tuple[str, str]] = []
    if daten or run.get("current"):
        abschnitte.append(("jetzt", "Jetzt"))
    if daten or verlauf_bilder:
        abschnitte.append(("verlauf", "Verlauf"))
    if normal_bilder or bilder["monat"]:
        abschnitte.append(("normal", "Normal"))
    if bilder["heuer"]:
        abschnitte.append(("heuer", "Heuer"))
    if bilder["reihe"] or bilder["lakes"]:
        abschnitte.append(("archiv", "Archiv"))

    daten_script = ""
    if daten:
        # Die Zahlen direkt in der Seite: kein zweiter Abruf, und sie lädt
        # auch aus einer Datei am Handy. "</" darf im Skriptblock nicht
        # vorkommen -- ein Seename könnte es theoretisch enthalten.
        payload = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))
        daten_script = ('<script type="application/json" id="aktuell-daten">'
                        + payload.replace("</", "<\\/") + "</script>")

    parts = [
        "<!doctype html>",
        '<html lang="de"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Kärntner Seen — Wassertemperatur</title>",
        '<meta name="description" content="Wie warm die Kärntner Seen gerade sind — '
        'und wie das gegenüber dem langjährigen Mittel dasteht.">',
        f"<style>{STYLE}</style></head><body>",
        topbar(abschnitte),
        '<main id="top">',
        '<header class="intro">',
        "<h1>Kärntner Seen</h1>",
        '<p class="lede">Wie warm die Seen gerade sind — und wie das gegenüber dem '
        f'langjährigen Mittel {esc(run.get("reference", ""))} dasteht.</p>',
        "</header>",
        banner,
        daten_script,
        jetzt_section(daten, run, heuer_keys),
        verlauf_section(daten, verlauf_bilder),
    ]

    if normal_bilder or bilder["monat"]:
        parts.append('<section id="normal">')
        parts.append("<h2>Gegen den Normalwert</h2>")
        for _prefix, title, caption, light, dark in normal_bilder + bilder["monat"]:
            parts += [f"<h3>{esc(title)}</h3>", f'<p class="caption">{esc(caption)}</p>',
                      picture(light, dark, title)]
        parts.append("</section>")

    # Das laufende Jahr je See -- der Übergang von heute zur langen Reihe.
    if bilder["heuer"]:
        jahr = run.get("current_year") or ""
        parts += ['<section id="heuer">',
                  f"<h2>{esc(jahr)} in Tageswerten</h2>",
                  '<p class="caption">Was heuer gemessen wurde, Tag für Tag gegen '
                  "den Monatsnormalwert. Die Reihe wächst mit jedem abgelegten "
                  "Abruf. Einen See antippen klappt sein Bild auf.</p>",
                  lake_details("heuer", bilder["heuer"], je_see),
                  "</section>"]

    # Zuletzt die amtliche lange Reihe. Sie endet mit dem letzten Jahrbuch,
    # taugt also zum Nachschlagen, nicht zur Auskunft über heute.
    if bilder["reihe"] or bilder["lakes"]:
        parts += ['<section id="archiv">',
                  "<h2>Die amtliche Reihe"
                  + (f" bis {esc(reihe_bis)}" if reihe_bis else "") + "</h2>",
                  '<p class="caption">Ab hier die langjährigen Messreihen: sie enden '
                  f"mit dem letzten Jahrbuch ({esc(run.get('data_until', ''))}), "
                  f"Vergleichsjahr ist {esc(year)}. Das laufende Jahr steht nicht in "
                  "ihnen — es steht oben.</p>"]
        for _prefix, title, caption, light, dark in bilder["reihe"]:
            parts += [f"<h3>{esc(title)}</h3>", f'<p class="caption">{esc(caption)}</p>',
                      picture(light, dark, title)]
        if bilder["lakes"]:
            parts += [f"<h3>Jahresgang je See {esc(year)}</h3>",
                      '<p class="caption">Der Verlauf des Jahres gegen den Normalwert, '
                      "das Band zeigt die Bandbreite des Bezugszeitraums.</p>",
                      lake_details("archiv", bilder["lakes"], {})]
        parts.append("</section>")

    parts.append('<section id="hintergrund">')
    parts.append(coverage_table(run))
    parts += [
        '<div class="meta"><dl>',
        f"<dt>Quelle</dt><dd>{esc(run.get('source', ''))}</dd>",
        f"<dt>Auflösung</dt><dd>{aufloesung}</dd>",
        f"<dt>Normalwert</dt><dd>{esc(run.get('method', ''))} über "
        f"{esc(run.get('reference', ''))}</dd>",
        f"<dt>Datenstand</dt><dd>{esc(run.get('data_until', ''))} "
        f"({werte} Werte ab {esc(run.get('data_from', ''))})</dd>",
        f"<dt>Erzeugt</dt><dd>{esc(generated)}</dd>",
        f"</dl>{notes_block}</div>",
        "</section>",
        "<footer>",
        "Erzeugt mit <a href=\"https://github.com/mgorfer/lake-temperature\">seetemp</a>. ",
        "Die Seite folgt der Hell/Dunkel-Einstellung des Geräts"
        + '<span class="js-only">, der Schalter oben rechts stellt sie um</span>. '
        "Favoriten und Einstellungen bleiben auf diesem Gerät. ",
        'Rohdaten des Laufs: <a href="run.json">run.json</a>'
        + (', <a href="aktuell.json">aktuell.json</a>' if daten else "") + ".",
        "</footer>",
        "</main>",
        '<button type="button" class="nach-oben js-only" id="nach-oben" aria-label="Nach oben">↑</button>',
        f"<script>{SCRIPT}</script>",
        "</body></html>",
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
