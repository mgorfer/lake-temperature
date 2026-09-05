# Wege zu den Daten — was geht und was nicht

Der Seendienst des Landes Kärnten antwortet Rechenzentren nicht. GitHub
Actions kommt also nicht an die aktuellen Werte, ein Gerät mit
österreichischem Anschluss schon. Diese Notiz hält fest, welche Umwege
geprüft wurden — damit niemand sie ein zweites Mal geht.

Alle Prüfungen liefen vom GitHub-Runner aus (`Quelle erkunden` →
`umwege`), Stand 04.09.2026.

## Geprüft und verworfen

| Weg | Ergebnis |
|---|---|
| **Internet-Archiv, vorhandene Aufnahmen** | Genau **eine** Aufnahme überhaupt (06.05.2024). Für eine Zeitreihe unbrauchbar. |
| **Internet-Archiv, frische Aufnahme** (Save Page Now) | **HTTP 523** — der Archiv-Crawler erreicht `info.ktn.gv.at` heute selbst nicht. |
| **GeoSphere Austria Data Hub** | Erreichbar, 67 Datensätze, **keiner** zu Seen oder Wassertemperatur. Meteorologie, nicht Hydrologie. |
| **Textspiegel r.jina.ai** | HTTP 422. |
| **eHYD als Tagesquelle** | Führt Wassertemperatur nur als `WT-Monatsmittel`. Die vollständige Dateiliste je Messstelle bestätigt: nichts Tägliches. |
| **Archiv des Landes** | Der Katalog auf data.gv.at weist alle zehn Ressourcen aus: die Sammeldateien tragen "Jetzt -24h", die Lite-Fassungen "letzter Messwert", die Datei je Messstelle "Jetzt -72h". Ein Archiv gibt es nicht. Vergangene Tage dieses Jahres sind über die offene Schnittstelle nicht mehr zu holen. |

Die eine Aufnahme von 2024 war nicht ganz umsonst: sie zeigt dasselbe
Feldschema wie heute. Der Aufbau des Dienstes ist also über zwei Jahre
stabil geblieben — das stützt die Annahme, dass der Adapter nicht bei der
nächsten Änderung auseinanderfällt.

## Was stattdessen trägt

Der unspektakuläre Weg: **das Gerät, das den Dienst erreicht, legt eine
Kopie im Projekt ab.**

```bash
python tools/snapshot_ktn.py        # holt und legt ab
git add data/aktuell && git commit -m "Messwerte vom ..." && git push
```

`./phone.sh` erledigt den ersten Schritt bei jedem Lauf von selbst. Die
Auswertung auf GitHub nimmt den jüngsten abgelegten Abruf, wenn der Dienst
schweigt, und schreibt dessen Alter in den Quellennamen und auf die
Grafik — „abgelegter Abruf (2 h alt)" statt „aktuell".

Das ist kein Notbehelf, sondern die sauberere Lösung: keine Abhängigkeit
von einem Dritten, keine Zweckentfremdung fremder Infrastruktur, und die
Daten kommen von dort, wo sie herkommen dürfen.

## Was noch offen wäre

* **Hydrographisches Jahrbuch** (`wasser.umweltbundesamt.at/hydjb`) ist
  erreichbar, aber eine Web-Anwendung für Berichte, keine Schnittstelle.
  Ob dort Tageswerte der Seetemperatur abrufbar sind, ist ungeprüft.
* **Anfrage beim Hydrographischen Dienst** (`abt12.post@ktn.gv.at`): ob
  Tagesmittel als lange Reihe abgegeben werden, und ob die Sperre gegen
  Rechenzentren beabsichtigt ist. Das ist die Frage, die ein Mensch
  stellen sollte, nicht ein Skript.
