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
| `01_uebersicht_abweichung_<Jahr>.png` | Alle Seen, mittlere Abweichung der Badesaison vom Normalwert |
| `02_monatsmatrix_<Jahr>.png` | Matrix See × Monat der Abweichungen |
| `03_badetage_<Jahr>.png` | Tage ≥ Schwelle, aktuelles Jahr gegen das langjährige Mittel |
| `04_saisonabweichung_zeitreihe.png` | Je See ein Kleindiagramm: jeder Sommer seit Reihenbeginn |
| `seen/<see>_<Jahr>.png` | Jahresgang eines Sees mit Normalwert, Perzentilband und Min/Max-Hülle |

Die Grafiken sind für beide Farbschemata getrennt abgestimmt; die Palette ist
gegen Farbfehlsichtigkeit geprüft, Abweichungen laufen über eine
divergierende Blau/Rot-Skala mit neutraler Mitte.

## Installation

```bash
pip install -r requirements.txt
```

## Verwendung

```bash
python -m seetemp --list-lakes                    # verfügbare Seen
python -m seetemp --source demo --year 2026       # alles, beide Farbschemata
python -m seetemp --source ehyd --ref 1991-2020   # echte Messreihen (Konfiguration nötig)
python -m seetemp --source csv --csv messwerte.csv --lakes woerthersee faaker_see
python -m seetemp --theme light --threshold 20 --out ./grafiken
```

Wichtige Schalter:

| Schalter | Bedeutung |
|---|---|
| `--source` | `demo`, `ehyd`, `kagis` oder `csv` |
| `--year` | Vergleichsjahr, Vorgabe: laufendes Jahr |
| `--ref VON-BIS` | Bezugszeitraum, Vorgabe `1991-2020` (WMO-Normalperiode) |
| `--window` | Halbe Breite des gleitenden Fensters in Tagen, Vorgabe 7 |
| `--min-samples` | Mindestzahl Werte je Kalendertag-Fenster, Vorgabe 20 |
| `--threshold` | Schwelle für die Badetage-Bilanz, Vorgabe 22 °C |
| `--theme` | `light`, `dark` oder `both` |

## Datenquellen

### `demo` (Vorgabe) — synthetisch, netzunabhängig

Ein deterministisches Jahresgangmodell erzeugt plausible Reihen ab 1991. Es
bildet Wärmeträgheit tiefer Seen, Höhenabhängigkeit, Witterungsrauschen und
einen Erwärmungstrend von rund +0,35 K pro Jahrzehnt ab.

**Das sind keine Messdaten.** Jede so erzeugte Grafik trägt den Wasserzeichen-
Hinweis `DEMO-DATEN`, und die Quellenzeile weist sie als synthetisch aus. Der
Modus ist dazu da, die Auswertung ohne Netzzugang vorführen und testen zu
können — nicht dazu, Aussagen über echte Seen zu treffen.

### `ehyd` — Hydrographischer Dienst Österreich

Der Weg zu echten langen Reihen. eHYD (`ehyd.gv.at`) exportiert Tageswerte
hydrographischer Messstellen als CSV; die App liest dieses Format
(ISO-8859-1, Dezimalkomma, `Lücke` als Fehlkennung).

Vor dem ersten Lauf muss in `config/stations.json` unter `ehyd.stations` je
See die HZB-Nummer der zugehörigen Seemessstelle eingetragen werden. Die
ausgelieferte Datei enthält bewusst **leere** Felder: eine geratene Nummer
würde stillschweigend die falsche Messstelle auswerten, deshalb bricht die
App bei leerer Konfiguration mit einem Hinweis ab statt zu raten. Auch die
URL-Vorlage ist konfigurierbar, falls sich das Exportschema ändert.

### `kagis` — aktuelle Seetemperaturen des Landes Kärnten

Liest einen ArcGIS-Feature-Dienst mit den tagesaktuellen
Oberflächentemperaturen. Dienst-URL, Feldnamen und die Zuordnung
Seename → Schlüssel stehen ebenfalls in `config/stations.json`. Diese Quelle
liefert nur den jüngsten Wert je See — sie ergänzt eHYD, ersetzt es nicht,
denn für ein langjähriges Mittel braucht es die lange Reihe.

### `csv` — eigene Messreihen

```csv
lake_key,date,temp_c
woerthersee,2024-07-01,24.8
woerthersee,2024-07-02,25.1
```

Deutsche Spaltennamen (`see`, `datum`, `temperatur`) werden ebenfalls erkannt.

## Methodik

* **Normalwert.** Für jeden Kalendertag wird das Mittel aller Werte gebildet,
  die im Bezugszeitraum in ein Fenster von ±7 Tagen um diesen Kalendertag
  fallen. Das Fenster ist zyklisch, der 1. Jänner greift also auch auf den
  Dezember zurück. So verschwindet die Tag-zu-Tag-Zufälligkeit einer einzelnen
  Reihe, ohne den Jahresgang zu verschleifen.
* **Bandbreite.** Neben dem Mittel werden Standardabweichung, 10./90.
  Perzentil und die Extremwerte des Bezugszeitraums geführt. Erst dadurch wird
  eine einzelne Abweichung einordenbar: +1 K im März heisst etwas anderes als
  +1 K im August.
* **Schaltjahre.** Der 29. Februar wird auf den 28. gelegt, damit alle Jahre
  dieselbe 365-Tage-Achse teilen.
* **Datenlücken.** Ein Kalendertag bekommt nur dann einen Normalwert, wenn im
  Fenster mindestens `--min-samples` Werte liegen. Tage ohne Normalwert
  bleiben in der Auswertung leer statt geschätzt zu werden.
* **Angebrochenes Jahr.** Läuft das Vergleichsjahr noch, wird die
  Badetage-Bilanz für alle Jahre am selben Kalendertag abgeschnitten — sonst
  stünde eine halbe Saison gegen eine ganze.
* **Einheiten.** Temperaturen in °C, Abweichungen in K (eine Differenz von
  Temperaturen ist eine Temperaturdifferenz, kein Temperaturwert).

## Tests

```bash
python -m unittest discover -s tests
```

Geprüft werden die Schaltjahr-Ausrichtung, das zyklische Fenster, die
Abweichungsrechnung, die Beschneidung des angebrochenen Jahres, die
Reproduzierbarkeit des Demomodells und der eHYD-Parser.

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
    ehyd.py         Hydrographischer Dienst Österreich
    kagis.py        Land Kärnten, aktuelle Werte
    csvfile.py      eigene CSV-Dateien
    synthetic.py    Demomodell (synthetisch)
config/stations.json  Stationszuordnung für die Online-Quellen
```
