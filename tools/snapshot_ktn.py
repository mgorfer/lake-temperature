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

from seetemp.cli import load_config  # noqa: E402
from seetemp.sources import ktn  # noqa: E402

CONFIG = Path(__file__).resolve().parent.parent / "config" / "stations.json"

#: So viele Abrufe bleiben liegen; ältere werden entfernt.
KEEP = 12


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=Path(ktn.SNAPSHOT_DIR))
    parser.add_argument("--keep", type=int, default=KEEP,
                        help=f"Anzahl aufzubewahrender Abrufe (Vorgabe {KEEP})")
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
