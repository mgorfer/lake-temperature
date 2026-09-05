"""Holt die aktuellen Seewerte und legt sie im Projekt ab.

Der Dienst des Landes Kärnten antwortet Rechenzentren nicht, einem
österreichischen Anschluss aber schon. Wer ihn erreicht, kann mit diesem
Werkzeug eine Kopie ablegen und einchecken -- dann rechnet auch die
Auswertung auf GitHub damit weiter, ehrlich beschriftet mit dem Alter der
Messwerte.

    python tools/snapshot_ktn.py
    git add data/aktuell && git commit -m "Messwerte vom ..." && git push
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seetemp.cli import load_config  # noqa: E402
from seetemp.sources import ktn  # noqa: E402

CONFIG = Path(__file__).resolve().parent.parent / "config" / "stations.json"

#: So viele Abrufe bleiben liegen; ältere werden entfernt. Die Tage gehen
#: dabei nicht verloren -- sie stehen in der fortgeschriebenen Tagesreihe
#: (data/aktuell/tagesreihe.csv), die dieses Werkzeug bei jedem Lauf
#: nachführt.
KEEP = 12

#: So viele Dateien je Messstelle. Zwei genügen: die Datei trägt 72
#: Stunden, zwei überlappen sich also reichlich.
KEEP_STATION = 2


def hole_stationen(payload, ziel: Path, keep: int) -> int:
    """Die 72-Stunden-Datei je Messstelle holen und ablegen.

    Ein Fehlschlag bei einer Messstelle beendet nichts: die übrigen sind
    deswegen nicht weniger wert. Gemeldet wird er trotzdem -- ein stiller
    Ausfall wäre schlimmer als ein lauter.
    """
    kennungen = ktn.station_ids(payload)
    if not kennungen:
        print("\nKeine Stationskennungen in der Antwort -- 72-Stunden-Dateien "
              "übersprungen.", file=sys.stderr)
        return 0

    ziel.mkdir(parents=True, exist_ok=True)
    geholt, werte, fehler = 0, 0, []
    for kennung, name in sorted(kennungen.items()):
        url = ktn.STATION_URL.format(id=kennung)
        try:
            antwort = requests.get(url, timeout=(10, 30))
            antwort.raise_for_status()
            daten = antwort.json()
        except (requests.RequestException, ValueError) as exc:
            fehler.append(f"{name or kennung}: {exc.__class__.__name__}")
            continue
        reihe = ktn.temperature_series(daten)
        if not reihe:
            # Abgelegt wird sie trotzdem: vielleicht heisst das Feld nur
            # anders, und die Rohantwort ist dann das, woran man es sieht.
            fehler.append(f"{name or kennung}: keine Temperaturreihe erkannt")
        werte += len(reihe)
        (ziel / ktn.station_snapshot_name(kennung)).write_text(
            json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        geholt += 1

        if keep:
            alt = sorted(ziel.glob(f"station-{kennung}-*.json"))[:-keep]
            for pfad in alt:
                pfad.unlink()

    print(f"\n{geholt} von {len(kennungen)} Messstellen als 72-Stunden-Datei "
          f"abgelegt ({werte} Einzelmessungen)")
    for zeile in fehler[:8]:
        print(f"  · {zeile}", file=sys.stderr)
    return geholt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=Path(ktn.SNAPSHOT_DIR))
    parser.add_argument("--keep", type=int, default=KEEP,
                        help=f"Anzahl aufzubewahrender Abrufe (Vorgabe {KEEP})")
    parser.add_argument("--keep-station", type=int, default=KEEP_STATION,
                        help=f"Dateien je Messstelle (Vorgabe {KEEP_STATION})")
    parser.add_argument("--daily", type=Path, default=Path(ktn.DAILY_CSV),
                        help="Fortgeschriebene Tagesreihe")
    parser.add_argument("--ohne-stationen", action="store_true",
                        help="nur die Sammeldatei holen, keine 72-Stunden-Dateien")
    args = parser.parse_args()

    config = load_config(args.config).get("ktn", {})
    url = args.url or config.get("url") or ktn.DEFAULT_URL

    try:
        response = requests.get(url, timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise SystemExit(
            f"Nicht erreichbar ({url}): {exc.__class__.__name__}: {exc}\n"
            "Aus Rechenzentren antwortet der Dienst nicht -- dieses Werkzeug "
            "gehört auf ein Gerät mit österreichischem Anschluss."
        ) from exc
    except ValueError as exc:
        raise SystemExit(f"Kein JSON: {exc}") from exc

    # Nur eine grobe Prüfung vor dem Ablegen: enthält die Antwort überhaupt
    # Messstellen? Die Zuordnung darf das Ablegen NICHT verhindern -- die
    # Rohantwort ist auch dann wertvoll, wenn ein Seename noch fehlt.
    stationen = ktn.records(payload)
    if not stationen:
        raise SystemExit("Antwort enthält keine Messstellen -- nicht abgelegt.")

    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / ktn.snapshot_name()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")

    alt = sorted(args.out.glob("hdkaernten_see-*.json"))[:-args.keep] if args.keep else []
    for path in alt:
        path.unlink()

    print(f"{target} ({target.stat().st_size // 1024} KiB, "
          f"{len(stationen)} Messstellen)")
    if alt:
        print(f"{len(alt)} ältere Abrufe entfernt")

    # Die Datei je Messstelle trägt 72 Stunden statt 24. Sie ist der
    # Grund, warum ein Abruf alle zwei Tage genügt -- und der einzige
    # Weg, einen verpassten Tag noch einzusammeln.
    if not args.ohne_stationen:
        hole_stationen(payload, args.out / "station", args.keep_station)

    # Was einmal gemessen wurde, soll bleiben, auch wenn die Rohabrufe
    # später aufgeräumt werden.
    vorher = len(ktn.read_daily(args.daily))
    tage = ktn.daily_table(args.out, config, args.daily)
    if not tage.empty:
        ktn.write_daily(tage, args.daily)
        spanne = pd.DatetimeIndex(tage["date"])
        print(f"\nTagesreihe: {len(tage)} Tageswerte "
              f"({len(tage) - vorher:+d}), {tage['lake_key'].nunique()} Seen, "
              f"{spanne.min():%d.%m.%Y} – {spanne.max():%d.%m.%Y}")
        print(f"  {args.daily}")

    try:
        data = ktn.load(payload, config)
    except SystemExit as exc:
        # Abgelegt ist abgelegt -- der Hinweis genügt.
        print(f"\nHinweis: {exc}", file=sys.stderr)
        return 0
    print(f"{len(data.frame)} davon einem See zugeordnet")
    for note in data.notes[:4]:
        print(f"  · {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
