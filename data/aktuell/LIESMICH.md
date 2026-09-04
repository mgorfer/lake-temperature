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

Lizenz der Daten: CC-BY-4.0, Land Kärnten, bezogen über data.gv.at.
Der Dienst weist sie als ungeprüfte Rohdaten aus.
