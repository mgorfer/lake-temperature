# Auf dem Handy laufen lassen

**Willst du die Bilder nur ansehen?** Dann brauchst du gar nichts zu
installieren — [Weg C](#weg-c-gar-nicht-lokal-rechnen--der-bequemste-weg) ist
ein Lesezeichen im Browser.

Kurz: **ja.** Es ist eine reine Kommandozeilen-App ohne Fenster — sie zeichnet
über das Backend `Agg` direkt in Dateien. Das läuft auf Android genauso wie
auf einem Rechner, es fehlt nur eine Kommandozeile. Dafür gibt es zwei Wege.

| | Termux | Samsung Linux Terminal |
|---|---|---|
| Geräte | jedes Galaxy | nur Exynos, MediaTek, Tensor — **nicht Snapdragon** |
| Android | ab 7 | 16 / One UI 8 aufwärts |
| Installation | Pakete aus dem Termux-Repo | `pip install` wie am PC |
| Aufwand | mittel | gering, wenn das Gerät es kann |

---

## Weg A: Termux — funktioniert auf jedem Galaxy

### Einmalig einrichten (rund 10 Minuten)

**1. Termux installieren** — aus [F-Droid](https://f-droid.org/packages/com.termux/),
**nicht** aus dem Play Store. Die Play-Store-Fassung wird seit Jahren nicht
mehr gepflegt und lässt sich mit den aktuellen Paketen nicht betreiben.

**2. Pakete installieren.** Ein Block, zum Kopieren:

```bash
pkg update -y && pkg upgrade -y
pkg install -y python matplotlib git gh termux-api
pkg install -y tur-repo && pkg install -y python-pandas
pip install python-dateutil requests
```

`matplotlib` zieht numpy, pillow und contourpy mit. `python-pandas` liegt
nicht im Hauptrepo, sondern im Termux User Repository — daher der Umweg über
`tur-repo`.

**3. Speicherzugriff freigeben:**

```bash
termux-setup-storage
```

Android fragt einmal nach; bestätigen. Ohne das rechnet alles korrekt, aber
die Galerie findet die Bilder nicht.

**4. Bei GitHub anmelden:**

```bash
gh auth login
```

Wählen: *GitHub.com* → *HTTPS* → *Login with a web browser*. Termux zeigt
einen achtstelligen Code, der Browser öffnet sich, Code eintippen, fertig.
**Kein Token abtippen, kein Schlüssel erzeugen** — `gh` richtet die
Git-Zugangsdaten selbst ein.

Das ist nur nötig, wenn du die Messwerte einchecken willst (Schritt `--push`
weiter unten). Zum blossen Rechnen reicht Schritt 1–3.

**5. Projekt holen:**

```bash
git clone https://github.com/mgorfer/lake-temperature
cd lake-temperature
```

### Ab dann: ein Befehl

```bash
cd lake-temperature && ./phone.sh --source ehyd --push
```

Das macht in einem Zug:

1. holt die **aktuellen Wassertemperaturen** beim Hydrographischen Dienst
   Kärnten (geht am Handy, weil dein Anschluss österreichisch ist),
2. legt sie unter `data/aktuell` ab,
3. holt die **amtlichen langen Reihen** von eHYD,
4. rechnet Normalwerte und Abweichungen,
5. schreibt die PNGs nach `~/storage/shared/Pictures/Seetemperaturen` und
   meldet sie der Galerie an,
6. checkt die Messwerte ein und pusht sie — womit auch die Auswertung auf
   GitHub Pages mit deinen frischen Werten rechnet.

Ohne `--push` entfällt nur Schritt 6.

### Varianten

```bash
./phone.sh                                  # Demodaten, ohne Netz
./phone.sh --source ehyd                    # rechnen, nicht einchecken
./phone.sh --source ehyd --lakes woerthersee faaker_see   # schneller
./phone.sh --source ehyd --theme dark
./phone.sh --source ehyd --current none     # ohne die aktuellen Werte
```

### Beim nächsten Mal

```bash
cd lake-temperature && git pull && ./phone.sh --source ehyd --push
```

`git pull` nur, wenn sich am Programm etwas geändert hat.

### Versionen im Termux-Repo (Stand September 2026)

| Paket | Version | Repo |
|---|---|---|
| `python` | 3.14.6 | Haupt |
| `python-numpy` | 2.4.4 | Haupt |
| `matplotlib` | 3.11.1 | Haupt |
| `python-pandas` | 3.0.5 | TUR |

Das deckt sich mit den Versionen, gegen die entwickelt wurde.

## Weg B: Samsung Linux Terminal — bequemer, aber nicht auf jedem Gerät

Ab Android 16 / One UI 8 bringt Samsung eine echte Debian-VM mit. Einschalten:

**Einstellungen → Entwickleroptionen → „Linux-Terminal"** (die
Entwickleroptionen erscheinen, wenn man in *Über das Telefon →
Softwareinformationen* siebenmal auf die Buildnummer tippt).

**Wichtige Einschränkung:** Das setzt einen Chipsatz voraus, der
nicht-geschützte virtuelle Maschinen erlaubt — Exynos, MediaTek oder Google
Tensor. Auf Snapdragon-Geräten bricht der Start mit „Non-protected VMs are not
supported on this device" ab. In Europa sind viele Galaxy-S-Modelle Exynos, in
den USA meist Snapdragon; ein Blick in die Modellnummer klärt es.

Läuft das Terminal, ist es ein gewöhnliches Debian:

```bash
sudo apt update
sudo apt install python3-pip python3-venv git
git clone https://github.com/mgorfer/lake-temperature
cd lake-temperature
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m seetemp --source ehyd
```

Der Haken: Die Debian-VM hat ihr eigenes Dateisystem. An die Bilder kommt man
über die Dateifreigabe des Terminals; ab One UI 8.5 ist der Zugriff auf den
Gerätespeicher erweitert worden.

---

## Weg C: gar nicht lokal rechnen — der bequemste Weg

Wenn es nur darum geht, die Bilder **am Handy zu sehen**, ist das Rechnen auf
dem Gerät der Umweg. Der Workflow
[`seetemperaturen.yml`](../.github/workflows/seetemperaturen.yml) rechnet auf
GitHub und veröffentlicht das Ergebnis als Seite:

**<https://mgorfer.github.io/lake-temperature/>**

Im Handy-Browser öffnen, „Zum Startbildschirm hinzufügen" — fertig. Kein
Termux, keine Pakete, keine Updates. Die Seite folgt der Hell/Dunkel-Einstellung
des Geräts, Antippen öffnet ein Bild in voller Auflösung.

Einmalig einzurichten: **Settings → Pages → Source: „GitHub Actions"**.
Danach läuft der Workflow montags früh, bei jeder Codeänderung und auf Zuruf
über *Actions → Seetemperaturen → Run workflow*.

---

## Was zu erwarten ist

Gemessen auf einem Container mit den oben genannten Versionen:

| Lauf | Dauer | Spitzenspeicher |
|---|---|---|
| alle 12 Seen, beide Farbschemata, 32 PNGs | 20 s | 279 MiB |
| ein See, ein Farbschema | 2 s | 154 MiB |

Auf einem Handy ist mit dem Zwei- bis Vierfachen der Zeit zu rechnen, also
etwa einer Minute für den vollen Lauf. Der Speicherbedarf ist für jedes
aktuelle Gerät unkritisch.

## Stolpersteine

* **Play-Store-Termux.** Führt zu Paketfehlern, die aussehen wie ein Problem
  dieser App. F-Droid nehmen.
* **`termux-setup-storage` vergessen.** Dann rechnet alles korrekt, aber die
  Galerie findet nichts. `phone.sh` weist darauf hin und legt die Bilder
  solange ins Projektverzeichnis.
* **`pip install pandas`** statt `pkg install python-pandas`: pip versucht dann,
  pandas aus dem Quelltext zu übersetzen. Das dauert auf einem Handy sehr lange
  und scheitert meist. Immer erst das Termux-Paket nehmen.
* **Push scheitert mit „Authentication failed".** Dann fehlt die Anmeldung:
  `gh auth login`. Ein von Hand angelegtes Token in die URL zu schreiben
  funktioniert zwar auch, steht dann aber im Klartext in der Git-Konfiguration.
* **Akku-Optimierung.** Android kann Termux im Hintergrund einfrieren. Für den
  vollen Lauf das Display anlassen oder in den Termux-Einstellungen einen
  Wakelock setzen.
