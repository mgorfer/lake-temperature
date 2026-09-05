# Abgelegte Abrufe des Kärntner Seendienstes

Der Dienst des Landes Kärnten antwortet Rechenzentren nicht -- GitHub Actions
kommt also nicht an die aktuellen Werte heran, ein Gerät mit
österreichischem Anschluss schon.

Dieses Verzeichnis überbrückt das: wer den Dienst erreicht, legt hier eine
Kopie ab und checkt sie ein.

    python tools/snapshot_ktn.py
    git add data/aktuell && git commit -m "Messwerte vom ..." && git push

Die Auswertung nimmt den jüngsten abgelegten Abruf, wenn der Dienst nicht
antwortet. Sie schreibt sein Alter in den Quellennamen und auf die Grafik --
ein drei Tage alter Wert erscheint als solcher, nicht als "aktuell".

`./phone.sh` legt bei jedem Lauf von selbst einen Abruf ab.

## Was hier liegt

| | |
|---|---|
| `hdkaernten_see-*.json` | die Sammeldatei über alle Seen, **letzte 24 h** |
| `station/station-<id>-*.json` | eine Datei je Messstelle, **letzte 72 h** |
| `tagesreihe.csv` | die fortgeschriebene Tagesreihe |

Die 72 Stunden sind der Grund, warum ein Abruf alle zwei Tage genügt statt
täglich einer. Weiter zurück gibt der Dienst nichts her: der Katalog auf
data.gv.at weist für alle seine Ressourcen "Jetzt -24h", "Jetzt -72h" oder
"letzter Messwert" aus. **Ein Archiv gibt es nicht.** Was heute nicht
abgerufen wird, ist in drei Tagen fort.

Deshalb `tagesreihe.csv`: die Rohabrufe werden nach einer Weile entfernt --
sonst wüchse das Projekt um Megabyte je Woche -- die Tage aber bleiben.
Taucht ein Tag zweimal auf, gewinnt der mit den meisten Einzelmessungen;
ein halb erwischter Tag verdrängt keinen ganzen.

Lizenz der Daten: CC-BY-4.0, Land Kärnten, bezogen über data.gv.at.
Der Dienst weist sie als ungeprüfte Rohdaten aus.
