# Kärntner Seen — Wassertemperatur im langjährigen Vergleich

Kommandozeilen-App, die die Wassertemperatur der Kärntner Seen gegen ein
langjähriges Mittel stellt und das Ergebnis als PNG ausgibt.

```
python -m seetemp --source demo --year 2026
```

Sprache: **Python**. Für diese Aufgabe passt es am besten — CSV- und
JSON-Quellen einlesen, Zeitreihen auf einen Kalendertag-Normalwert
umrechnen und daraus druckfähige PNGs erzeugen, ist genau das, wofür
pandas/matplotlib da sind.

---

## Was herauskommt

Je Farbschema (`output/light/`, `output/dark/`):

| Datei | Inhalt |
|---|---|
| `00_letzte_72h.png` | Alle Seen in Einzelmessungen der letzten 72 Stunden (nur mit `--current ktn`) |
| `00_aktuell.png` | Aktuelle Werte je See gegen ihren Normalwert (nur mit `--current ktn`) |
| `01_uebersicht_abweichung_<Jahr>.png` | Alle Seen, mittlere Abweichung der Badesaison vom Normalwert |
| `02_monatsmatrix_<Jahr>.png` | Matrix See × Monat der Abweichungen |
| `03_badetage_<Jahr>.png` | Tage ≥ Schwelle, aktuelles Jahr gegen das langjährige Mittel |
| `04_saisonabweichung_zeitreihe.png` | Je See ein Kleindiagramm: jeder Sommer seit Reihenbeginn |
| `05_<monat>_je_jahr.png` | Ein Kalendermonat über alle Jahre der Aufzeichnung, je See ein Feld (`--month`, Vorgabe August) |
| `seen/<see>_<Jahr>.png` | Jahresgang eines Sees mit Normalwert, Perzentilband und Min/Max-Hülle |
| `seen/<see>_heuer.png` | Das laufende Jahr in Tageswerten gegen den Monatsnormalwert (nur mit `--current ktn`) |

Die Reihenfolge folgt dem Interesse: **ganz vorne das aktuelle Geschehen.**
`00_letzte_72h.png` legt alle Seen in Einzelmessungen auf eine Achse — wo es
gerade warm ist und wie der Tagesgang läuft, drei Tage weit zurück. Fünfzehn
Seen vertragen keine fünfzehn Farben: die Farbe folgt allein der Temperatur,
und wer welcher See ist, steht als Name am rechten Rand neben seiner Linie.
Dann `00_aktuell.png`, dann der Blick über die Jahre
(`05_<monat>_je_jahr.png`) — und erst am Ende der Seite die amtliche lange
Reihe, die mit dem letzten Jahrbuch endet.

Die gemeinsame Jahresachse des Monatsvergleichs beginnt mit dem ersten Jahr,
in dem der **Wörthersee** diesen Monat belegt hat — die längste Reihe setzt
den Ausschnitt, in dem sich alle übrigen Seen einordnen. Reicht ein anderer
See noch weiter zurück, fallen seine früheren Werte heraus; wie viele, sagt
der Untertitel der Grafik, damit nichts stillschweigend verschwindet.

Die amtliche Reihe endet mit dem letzten Jahrbuch — eHYD führt die
Wassertemperatur derzeit bis 2023. Das laufende Jahr steht deshalb nicht in
ihr, sondern allein in den abgelegten Abrufen des Landesdienstes unter
`data/aktuell/`. `seen/<see>_heuer.png` setzt beides zusammen: der
Normalwert als Treppe über das Jahr — er ist ein Monatsmittel und wird auch
als solches gezeichnet, nicht zu einer Kurve verschliffen, die er nicht ist
— und darüber die gemessenen Tagesmittel. Die Reihe wächst mit jedem
abgelegten Abruf.

Der Dienst des Landes gibt zwei Fassungen ab: die Sammeldatei über alle
Seen trägt die letzten **24 Stunden**, die Datei je Messstelle
(`.../json/station/<id>.json`) die letzten **72 Stunden**. Beide werden
abgerufen; die 72 Stunden sind der Grund, warum ein Abruf alle zwei Tage
genügt statt täglich einer. Ein Archiv gibt es nicht — was heute nicht
abgerufen wird, ist in drei Tagen fort.

Damit die Reihe nicht davon abhängt, welche Rohabrufe gerade herumliegen,
wird sie fortgeschrieben: `data/aktuell/tagesreihe.csv` sammelt Tag für
Tag, was je gemessen wurde. Taucht ein Tag zweimal auf, gewinnt der mit
den meisten Einzelmessungen — ein halb erwischter Tag verdrängt keinen
ganzen. Die Rohabrufe dürfen danach aufgeräumt werden.

Die Grafiken sind für beide Farbschemata getrennt abgestimmt; die Palette ist
gegen Farbfehlsichtigkeit geprüft, Abweichungen laufen über eine
divergierende Blau/Rot-Skala mit neutraler Mitte.

## Installation

```bash
pip install -r requirements.txt
```

Am Android-Handy geht das auch — siehe [docs/ANDROID.md](docs/ANDROID.md);
`./phone.sh` legt die Bilder dort direkt in die Galerie. Wer gar nichts
installieren will, nimmt die [automatisch veröffentlichte Seite](#automatisch-auf-github-pages).

## Verwendung

```bash
python -m seetemp --list-lakes                    # verfügbare Seen
python -m seetemp --source demo --year 2026       # alles, beide Farbschemata
python -m seetemp --source ehyd --ref 1991-2020   # amtliche Messreihen (HZB-Nummern sind hinterlegt)
python -m seetemp --source csv --csv messwerte.csv --lakes woerthersee faaker_see
python -m seetemp --theme light --threshold 20 --out ./grafiken
```

Wichtige Schalter:

| Schalter | Bedeutung |
|---|---|
| `--source` | `demo`, `ehyd`, `ktn` oder `csv` |
| `--year` | Vergleichsjahr, Vorgabe: das jüngste Jahr mit Daten |
| `--ref VON-BIS` | Bezugszeitraum, Vorgabe `1991-2020` (WMO-Normalperiode) |
| `--window` | Halbe Breite des gleitenden Fensters in Tagen, Vorgabe 7 |
| `--min-samples` | Mindestzahl Werte je Stützstelle, Vorgabe 20 (Tages-) bzw. 10 (Monatswerte) |
| `--resolution` | `auto` (aus der Quelle), `daily` oder `monthly` |
| `--threshold` | Schwelle für die Badetage-Bilanz, Vorgabe 22 °C |
| `--month` | Monat für `05_<monat>_je_jahr.png`, 1–12, Vorgabe 8 (August) |
| `--theme` | `light`, `dark` oder `both` |
| `--current` | `ktn` holt zusätzlich die aktuellen Werte des Landes Kärnten |
| `--probe` | nur nachsehen, was eHYD je Messstelle anbietet (keine Grafiken) |

## Automatisch auf GitHub Pages

Der Workflow [`.github/workflows/seetemperaturen.yml`](.github/workflows/seetemperaturen.yml)
rechnet die Auswertung und veröffentlicht sie als Seite:

**<https://mgorfer.github.io/lake-temperature/>**

Eine Seite in einer Spalte, Bilder in voller Breite, Antippen öffnet die
Originalauflösung — gedacht als Lesezeichen am Handy. Oben die letzten 72
Stunden samt Zahlentabelle, unten die lange Reihe; wer die Seite aufruft,
will meist zuerst wissen, wie warm es *jetzt* ist. Liegen beide
Farbschemata vor, wählt der Browser über `prefers-color-scheme` selbst; die
Seite folgt also der Systemeinstellung, ohne Schalter und ohne JavaScript.

Einmalige Einrichtung: **Settings → Pages → Source: „GitHub Actions"**.

| Auslöser | Wann | Quelle |
|---|---|---|
| `workflow_dispatch` | von Hand, mit Auswahl von Quelle, Jahr, Bezugszeitraum | frei wählbar |
| `schedule` | montags früh | `ehyd` |
| `push` | bei Änderungen an Code oder Konfiguration | `ehyd` |

Wöchentlich reicht, weil eHYD die Wassertemperatur als Monatsmittel führt —
häufiger abzurufen brächte keine neuen Werte. Die aktuellen Werte des Landes
Kärnten sind im Workflow abschaltbar und standardmässig aus: der Dienst
antwortet den Adressen von GitHub Actions nicht.

**Kein stiller Rückfall auf Demodaten.** Ist eHYD nicht erreichbar, schlägt der
Lauf fehl und die zuletzt veröffentlichte Seite bleibt stehen. Eine Seite mit
erfundenen Zahlen wäre schlechter als eine Seite von gestern. Wer Demodaten
sehen will, startet den Workflow von Hand mit `source: demo` — die Seite trägt
dann einen unübersehbaren Warnhinweis.

Jeder Lauf schreibt neben den PNGs eine `run.json` mit Quelle, Auflösung,
Bezugszeitraum, Datenstand und Dateiliste; daraus bauen
`tools/build_gallery.py` die Seite und `tools/summary.py` die Zusammenfassung
im Actions-Protokoll.

## Datenquellen

### Empfehlung: eHYD für die lange Reihe, Kärnten für die Aktualität

Für „Wassertemperatur gegen langjähriges Mittel" braucht es zwei Dinge, die
keine einzelne Quelle gleich gut liefert: **Jahrzehnte** für den Normalwert und
**Aktualität** für den Vergleichswert.

| | [eHYD](https://ehyd.gv.at/) | [Hydrographischer Dienst Kärnten](https://hydrographie.ktn.gv.at/gewasser/seen-wassertemperatur) |
|---|---|---|
| Betreiber | BMLUK, Hydrographie Österreich | Amt der Kärntner Landesregierung, Abt. 12 |
| Reichweite | gesamte Beobachtungsdauer der Messstelle | aktuelles Messfenster |
| Auflösung | **WT-Monatsmittel** | 15-Minuten-Werte |
| Zeitraum je Abruf | die ganze Reihe bis 2023 | 24 h (Sammeldatei), **72 h** (je Messstelle) |
| Format | CSV (ISO-8859-1, Dezimalkomma) | JSON/GeoJSON |
| Rolle hier | Normalwert **und** Vergleich | Tagesaktualität |

Beide sind amtlich, dauerhaft betrieben und über
[data.gv.at](https://www.data.gv.at/datasets/bf851ec0-94cb-43ca-83cb-a9dc96ddea51?locale=de)
unter CC-BY 4.0 veröffentlicht. Als Zweitmeinung zu einzelnen Jahren gibt es
das [Hydrographische Jahrbuch](https://wasser.umweltbundesamt.at/hydjb/)
(ab 2014; [Archiv 1893–2013](https://wasser.gv.at/hydjb/historic/historic.xhtml))
und für Kärnten die Auswertung
[„Wasser in Kärnten 1991–2020"](https://hydrographie.ktn.gv.at/informationen?nid=10) —
genau die Normalperiode, die diese App als Vorgabe verwendet.

### `ehyd` — eingerichtet und einsatzbereit

Seemessstellen liegen im Bereich Oberflächenwasser (Feld `owf`). Die
HZB-Nummern der Kärntner Seen sind in `config/stations.json` bereits
eingetragen:

Neun Seen führen bei eHYD eine Temperaturreihe — am laufenden Dienst
geprüft, nicht angenommen:

| See | HZB | Messstelle |
|---|---|---|
| Wörther See | 212985 | Pörtschach am Wörther See |
| Ossiacher See | 213272 | St. Andrä-OWF |
| Millstätter See | 212514 | Millstatt (See) |
| Faaker See | 212795 | Faak (Bundessportheim) |
| Klopeiner See | 213348 | Unterburg |
| Weißensee | 212563 | Techendorf |
| Keutschacher See | 213488 | Keutschach (See) |
| Längsee | 213801 | St. Georgen |
| Pressegger See | 212746 | Presseggen |

Sieben weitere Kärntner Seen bleiben ohne langjähriges Mittel, jeder aus
einem anderen Grund:

| See | HZB | Warum nicht |
|---|---|---|
| Gösselsdorfer See | 213579 | eHYD führt nur den Wasserstand |
| Turnersee | 217331 | stellt über eHYD keine Dateien bereit |
| Afritzer See | 217257 | dito |
| Feldsee (Brennsee) | 217273 | dito |
| Maltschacher See | 217265 | dito |
| Rauschele See | — | keine HZB-Nummer |
| Magdalensee | — | keine amtliche Messstelle bekannt |

**Aktuelle Werte liefert der Kärntner Dienst für all diese Seen trotzdem** —
sie erscheinen in `00_aktuell.png` mit ihrer Temperatur, nur ohne
Vergleichswert.

Der Abruf läuft über
`https://ehyd.gv.at/services/MessstellenExtraData/owf?id=<HZB>&file=<n>`.
(Die in älteren Anleitungen genannte Form `/eHYD/…` liefert keinen
Dateianhang mehr.) Die
Dateinummer `n` ist je Messstelle verschieden — welche Dateien es gibt, hängt
vom Messstellentyp ab. Sie wird deshalb **nicht geraten, sondern zur Laufzeit
ermittelt**: eHYD nennt den Dateinamen im Header `Content-Disposition`, und
gesucht wird die Datei, deren Name auf die Wassertemperatur verweist
(`WT-Monatsmittel-<HZB>.csv`).

```bash
python -m seetemp --source ehyd --year 2026
python -m seetemp --source ehyd --probe    # nachsehen, was eHYD anbietet
```

`--probe` fragt je Messstelle beide URL-Formen ab und berichtet, was
zurückkommt. Das unterscheidet die Fälle, die im Ergebnis gleich aussehen,
aber ganz verschiedene Reaktionen verlangen: veraltete URL-Vorlage,
Messstelle ohne Dateien, Messstelle ohne Temperaturreihe. Die Deutung
berücksichtigt dabei, ob dieselbe Vorlage anderswo funktioniert hat — sonst
hiesse „keine Dateien" fälschlich „falsche URL". Scheitert der Abruf
in der GitHub Action, läuft die Diagnose automatisch mit und steht in der
Zusammenfassung des Laufs.

**Zwei Eigenheiten der Quelle**, beide am laufenden Dienst überprüft:

*Die Reihen hinken nach.* Sie folgen dem Jahrbuch-Zyklus und enden derzeit
mit 2023, reichen dafür aber weit zurück — die älteste Kärntner Seereihe
beginnt im November 1910. Deshalb ist die Vorgabe für `--year` nicht das
laufende Kalenderjahr, sondern das jüngste Jahr mit Daten; die App sagt beim
Lauf, welches sie genommen hat. Wer tagesaktuelle Werte braucht, nimmt den
Dienst des Landes Kärnten.

*Die Auflösung ist monatlich.* eHYD führt die Wassertemperatur als
Monatsmittel. Die App erkennt das am Abstand der Zeitstempel, bildet den
Normalwert dann je Monat statt je Kalendertag und lässt die Badetage-Bilanz
aus — einzelne Badetage lassen sich aus einem Monatsmittel nicht zählen. Wer
tägliche Werte braucht, bekommt sie beim Hydrographischen Dienst Kärnten oder
auf Anfrage bei `abt12.post@ktn.gv.at`.

### `ktn` — aktuelle Werte des Landes Kärnten

Rund 250 Messstellen, 30-Minuten-Takt. Die Adresse stammt aus dem Katalog von
data.gv.at, Datensatz
[„Hydrographische Daten Kärnten"](https://www.data.gv.at/datasets/bf851ec0-94cb-43ca-83cb-a9dc96ddea51?locale=de):

```
https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json
```

Diese Quelle liefert den jüngsten Wert je See. Ihr eigentlicher Zweck ist
nicht der Alleinbetrieb, sondern die **Ergänzung**: eHYD stellt den
Normalwert, Kärnten den heutigen Stand.

```bash
python -m seetemp --source ehyd --current ktn   # das ist der interessante Fall
python -m seetemp --source ktn                  # nur die aktuellen Werte
```

Der Dienst liefert GeoJSON mit 15 Seestationen. Je Station stehen darin der
jüngste Messwert, eine **Messreihe der letzten rund 24 Stunden** im Viertel-
bis Halbstundentakt — und die **HZB-Nummer**. Letztere ist dieselbe Kennung
wie bei eHYD und damit die verlässlichste Zuordnung: sie überlebt jede
Umbenennung. Der Seename dient nur als Rückfall.

Aus der Messreihe bildet die App ein **Tagesmittel der letzten 24 Stunden**.
Nur das lässt sich mit einem Normalwert vergleichen, der selbst ein Mittel
über einen Tag ist; ein einzelner Momentwert trüge den Tagesgang mit hinein.
Der jüngste Einzelwert bleibt erhalten — er beantwortet die andere Frage,
nämlich wie warm es *gerade* ist.

Die Einzelmessungen selbst gehen nicht verloren: aus ihnen entsteht
`00_letzte_72h.png`, die Übersicht ganz vorne. Gezählt wird das Fenster ab
der jüngsten Messung im Bestand, nicht ab der Uhr des Rechners — sonst
schrumpfte das Bild mit jeder Stunde, die ein Abruf altert.

Daraus entsteht `00_aktuell.png` mit drei Grössen auf **einer** Achse: der
Balken ist das 24-Stunden-Mittel, die Marke sitzt auf dem Normalwert, der
Punkt auf dem jüngsten Einzelwert. Der Unterschied ist farbig — warm, wenn es
wärmer ist als üblich, blass blau für das, was zum Normalwert fehlt. Seen
ohne lange Reihe erscheinen mit ihrer Temperatur, aber ohne Vergleichswert;
eine Temperatur ohne Einordnung ist immer noch eine Temperatur.

Der Dienst kennzeichnet seine Werte als **ungeprüfte Rohdaten**. Dieser
Hinweis wird nicht verschluckt: er steht in der Ausgabe, in `run.json`, unter
der Grafik und auf der Seite.

**Der Dienst antwortet Rechenzentrums-Adressen nicht.** Aus GitHub Actions
heraus laufen alle `ktn.gv.at`-Adressen in einen TCP-Zeitablauf, auch die
Startseite — aus einem österreichischen Anschluss funktioniert es in der
Regel.

Vier Umwege wurden geprüft und sind Sackgassen (Internet-Archiv, GeoSphere,
Textspiegel, eHYD als Tagesquelle) — nachzulesen samt Messergebnissen in
[docs/DATENWEGE.md](docs/DATENWEGE.md). Was trägt, ist der unspektakuläre
Weg: **das Gerät, das den Dienst erreicht, legt eine Kopie im Projekt ab.**

```bash
python tools/snapshot_ktn.py     # holt und legt unter data/aktuell ab
git add data/aktuell && git commit -m "Messwerte vom ..." && git push
```

`./phone.sh` erledigt das bei jedem Lauf von selbst; mit `--push` auch das
Einchecken. Es meldet jeden Schritt mit Uhrzeit und schreibt `phone.log` mit,
und kein Schritt, der von aussen abhängt, läuft ohne Zeitlimit. Die Auswertung auf
GitHub nimmt dann den jüngsten abgelegten Abruf und schreibt dessen Alter
in den Quellennamen und auf die Grafik — „abgelegter Abruf (2 h alt)" statt
„aktuell". Ein alter Wert erscheint als alter Wert.

Schlägt beides fehl, bleibt die langjährige Auswertung gültig; der
Fehlschlag steht in der Ausgabe und in `run.json`. Selbst prüfen:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json
```

Das Feldschema ist nirgends dokumentiert; die Tests laufen deshalb gegen
einen Auszug der echten Antwort in `tests/fixtures/`. Der Adapter legt sich
trotzdem nicht darauf fest: er erkennt die Felder an ihren Namen
(deutsche Schreibweisen und Umschriften fallen zusammen, „Wörthersee" und
„Woerthersee" also auch), und findet er sie nicht, nennt er die tatsächlich
vorhandenen Felder samt Beispielsatz. Feste Namen lassen sich in
`config/stations.json` unter `ktn.fields` hinterlegen.

Was der Dienst gerade liefert, zeigt:

```bash
python tools/probe_ktn.py
```

### `csv` — eigene Messreihen

```csv
lake_key,date,temp_c
woerthersee,2024-07-01,24.8
woerthersee,2024-07-02,25.1
```

Deutsche Spaltennamen (`see`, `datum`, `temperatur`) werden ebenfalls erkannt.
Bei Monatsmitteln `--resolution monthly` mitgeben.

### `demo` (Vorgabe) — synthetisch, netzunabhängig

Ein deterministisches Jahresgangmodell erzeugt plausible Reihen ab 1991. Es
bildet Wärmeträgheit tiefer Seen, Höhenabhängigkeit, Witterungsrauschen und
einen Erwärmungstrend von rund +0,35 K pro Jahrzehnt ab.

**Das sind keine Messdaten.** Jede so erzeugte Grafik trägt den Wasserzeichen-
Hinweis `DEMO-DATEN`, und die Quellenzeile weist sie als synthetisch aus. Der
Modus ist dazu da, die Auswertung ohne Netzzugang vorführen und testen zu
können — nicht dazu, Aussagen über echte Seen zu treffen.

## Methodik

* **Normalwert (Tageswerte).** Für jeden Kalendertag wird das Mittel aller Werte gebildet,
  die im Bezugszeitraum in ein Fenster von ±7 Tagen um diesen Kalendertag
  fallen. Das Fenster ist zyklisch, der 1. Jänner greift also auch auf den
  Dezember zurück. So verschwindet die Tag-zu-Tag-Zufälligkeit einer einzelnen
  Reihe, ohne den Jahresgang zu verschleifen.
* **Normalwert (Monatsmittel).** Liefert die Quelle nur Monatswerte — wie
  eHYD —, ist der Monat selbst die Stützstelle; ein gleitendes Fenster wäre
  dort sinnlos. Die App erkennt die Auflösung am Abstand der Zeitstempel,
  `--resolution` überschreibt sie.
* **Bandbreite.** Neben dem Mittel werden Standardabweichung, 10./90.
  Perzentil und die Extremwerte des Bezugszeitraums geführt. Erst dadurch wird
  eine einzelne Abweichung einordenbar: +1 K im März heisst etwas anderes als
  +1 K im August.
* **Schaltjahre.** Der 29. Februar wird auf den 28. gelegt, damit alle Jahre
  dieselbe 365-Tage-Achse teilen.
* **Datenlücken.** Ein Kalendertag bekommt nur dann einen Normalwert, wenn im
  Fenster mindestens `--min-samples` Werte liegen. Tage ohne Normalwert
  bleiben in der Auswertung leer statt geschätzt zu werden.
* **Belegung.** Die Messreihen beginnen unterschiedlich früh: der Ossiacher
  See reicht bis 1910 zurück, der Pressegger See erst bis Juli 2009. Ein
  Normalwert aus zwölf Jahren ist keiner aus dreissig, und das soll nicht in
  der Zahl verschwinden. Deshalb steht die Belegung je See in der Kopfzeile
  des Jahresgangs, dünn belegte Seen tragen in der Übersicht einen Stern mit
  auflösender Fussnote, und die Seite führt eine Tabelle „Grundlage der
  Normalwerte". Als dünn gilt weniger als `MIN_YEARS` (20) Jahre.
* **Angebrochenes Jahr.** Läuft das Vergleichsjahr noch, wird die
  Badetage-Bilanz für alle Jahre am selben Kalendertag abgeschnitten — sonst
  stünde eine halbe Saison gegen eine ganze.
* **Einheiten.** Temperaturen in °C, Abweichungen in K (eine Differenz von
  Temperaturen ist eine Temperaturdifferenz, kein Temperaturwert).

## Tests

```bash
python -m unittest discover -s tests
```

99 Tests: Schaltjahr-Ausrichtung, zyklisches Fenster, Abweichungsrechnung,
Monatsauflösung, Beschneidung des angebrochenen Jahres, Reproduzierbarkeit des
Demomodells, eHYD-Parser und Dateierkennung , die Unterscheidung von toter
URL und fehlender Reihe sowie die Übersichtsseite (Hell/Dunkel-Umschaltung,
fehlende Grafiken, Maskierung, Demo-Warnung), die Wahl des
Vergleichsjahres sowie die Kärntner Quelle: das echte GeoJSON-Schema
(gegen einen Auszug der tatsächlichen Antwort), Zuordnung über die
HZB-Nummer mit Namensrückfall, das 24-Stunden-Mittel, ISO-Zeitstempel ohne
Tag-zuerst-Verdrehung, Mitternachtswerte ohne Datumssprung, Felderkennung,
Umlaut-Umschrift, Meldung bei unbekanntem Schema, Seen ohne lange Reihe sowie die abgelegten
Abrufe samt ehrlicher Altersangabe und die Belegung der Normalwerte.

Dazu die Übersicht der letzten 72 Stunden: das Fenster ab der jüngsten
Messung statt ab der Rechneruhr, dieselbe Messung aus zwei Abrufen als eine,
fünfzehn Seen ohne ausgehende Farben, das Auseinanderschieben der
Beschriftungen ohne Vertauschung — und die Reihenfolge der Seite: vorne die
letzten Stunden, hinten die amtliche Reihe.

## Aufbau

```
seetemp/
  lakes.py          Stammdaten der Seen
  climatology.py    Normalwerte, Abweichungen, Badetage
  charts.py         PNG-Erzeugung
  theme.py          Farben und Typografie (hell/dunkel)
  cli.py            Kommandozeile
  sources/
    base.py         gemeinsamer Datenvertrag
    ehyd.py         eHYD -- amtliche lange Reihen (Monatsmittel)
    ktn.py          Hydrographischer Dienst Kärnten, aktuelle Werte
    csvfile.py      eigene CSV-Dateien
    synthetic.py    Demomodell (synthetisch)
config/stations.json  Stationszuordnung für die Online-Quellen
phone.sh              Ein-Befehl-Start für Termux (Android)
docs/ANDROID.md       Einrichtung am Handy
tools/probe_ktn.py      Katalog und Dienst des Landes Kärnten erkunden
tools/probe_more.py     Umwege zu den Daten abklopfen
tools/snapshot_ktn.py   aktuelle Werte holen und im Projekt ablegen
data/aktuell/           abgelegte Abrufe (siehe LIESMICH.md dort)
docs/DATENWEGE.md       welche Wege geprüft wurden und warum sie scheitern
tools/build_gallery.py  Übersichtsseite aus einem Ausgabeverzeichnis
tools/summary.py        Lauf-Zusammenfassung für GitHub Actions
.github/workflows/      Rechnen und Veröffentlichen auf GitHub Pages
```
