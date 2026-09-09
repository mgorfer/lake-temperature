# Hinweise für Claude Code

Absprachen zu diesem Projekt, damit sie nicht in jeder Sitzung neu
verhandelt werden müssen.

## Ablauf: Branch, PR, Merge

Der Default-Branch heisst `claude/kaerntner-seen-temperatur-app-6pgtdh` —
es gibt kein `main`. Entwickelt wird auf einem eigenen Zweig, dann PR
gegen den Default-Branch.

**Fertige PRs dieses Projekts dürfen ohne Rückfrage gemergt werden**
(Merge-Commit, kein Squash). Fertig heisst: Tests grün, `output/` passend
neu gerechnet, und die Beschreibung sagt, was geprüft wurde. Ist ein PR
bereits gemergt, wird für Nacharbeiten ein neuer eröffnet — der Zweig
setzt dazu auf dem gemergten Stand neu auf.

Kein `--force` auf fremde Zweige; auf dem eigenen nur mit
`--force-with-lease`.

## Vor jedem Push

```bash
python -m unittest discover -s tests
```

Ändern sich Grafiken, `run.json` oder die Übersichtsseite, wird `output/`
neu gerechnet und mitgecheckt — die Seite im Repo soll zum Code passen:

```bash
python -m seetemp --source demo --current ktn --out output
python tools/build_gallery.py output
```

`--source demo`, weil aus der Arbeitsumgebung weder eHYD (`ehyd.gv.at`)
noch der Landesdienst (`info.ktn.gv.at`) erreichbar sind. Die aktuellen
Werte kommen dann aus den abgelegten Abrufen unter `data/aktuell/` — die
sind echt, auch wenn die Normalwerte aus dem Demomodell stammen.
**Kein stiller Rückfall auf Demodaten in der Veröffentlichung:** der
Workflow rechnet mit `ehyd` und schlägt lieber fehl, als eine Seite mit
erfundenen Zahlen zu bauen.

## Sprache und Stil

Alles auf Deutsch: Code-Kommentare, Docstrings, Commit-Nachrichten,
PR-Beschreibungen, README. Bezeichner im Code sind deutsch, wo es der
Sache dient (`reihe`, `kanten`, `frueher`), englisch dort, wo der
Datenvertrag es vorgibt (`lake_key`, `temp_c`).

Kein `ß` im Fliesstext (`heisst`, `aussen`, `muss`) — in Seenamen bleibt
es stehen (`Weißensee`). Zahlen in Grafiken mit Dezimalkomma und echtem
Minus (`charts.num()`).

Kommentare erklären das *Warum*, nicht das *Was* — besonders bei allem,
was gegen eine Falle gebaut ist (Zeitzonen, `dayfirst`, Wasserstand statt
Temperatur). Was verloren gehen oder falsch verstanden werden kann, wird
im Bild und in der Doku benannt, nicht beschönigt.
