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

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seetemp.sources import ktn  # noqa: E402

#: So viele Abrufe bleiben liegen; ältere werden entfernt.
KEEP = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=ktn.DEFAULT_URL)
    parser.add_argument("--out", type=Path, default=Path(ktn.SNAPSHOT_DIR))
    parser.add_argument("--keep", type=int, default=KEEP,
                        help=f"Anzahl aufzubewahrender Abrufe (Vorgabe {KEEP})")
    args = parser.parse_args()

    try:
        response = requests.get(args.url, timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise SystemExit(
            f"Nicht erreichbar: {exc.__class__.__name__}: {exc}\n"
            "Aus Rechenzentren antwortet der Dienst nicht -- dieses Werkzeug "
            "gehört auf ein Gerät mit österreichischem Anschluss."
        ) from exc
    except ValueError as exc:
        raise SystemExit(f"Kein JSON: {exc}") from exc

    # Erst prüfen, dann ablegen: eine unbrauchbare Datei einzuchecken hilft
    # niemandem.
    data = ktn.load(payload, {})
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / ktn.snapshot_name()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")

    alt = sorted(args.out.glob("hdkaernten_see-*.json"))[:-args.keep] if args.keep else []
    for path in alt:
        path.unlink()

    print(f"{target} ({target.stat().st_size // 1024} KiB, "
          f"{len(data.frame)} Stationen zugeordnet)")
    if alt:
        print(f"{len(alt)} ältere Abrufe entfernt")
    for note in data.notes[:4]:
        print(f"  · {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
