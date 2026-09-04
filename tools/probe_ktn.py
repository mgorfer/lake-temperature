"""Erkundet den offenen Datensatz des Hydrographischen Dienstes Kärnten.

Die URL des JSON-Dienstes steht nicht im Code, sondern im Katalog von
data.gv.at. Dieses Werkzeug fragt den Katalog ab, listet die Ressourcen und
sieht sich die JSON-Dienste an: Aufbau, Feldnamen, ein Beispielsatz. Damit
lässt sich die Zuordnung in config/stations.json belegen statt raten.

    python tools/probe_ktn.py
"""

from __future__ import annotations

import json
import sys

import requests

CKAN = "https://www.data.gv.at/katalog/api/3/action/package_show"
#: Datensätze des Landes Kärnten, die den Wasserkreislauf abdecken.
DATASETS = {
    "Hydrographische Daten Kärnten": "bf851ec0-94cb-43ca-83cb-a9dc96ddea51",
}
TIMEOUT = 45
#: Ressourcen, die nach Seen klingen, zuerst ansehen.
LAKE_HINTS = ("see", "seen", "lake")


def resources(dataset_id: str) -> list[dict]:
    response = requests.get(CKAN, params={"id": dataset_id}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise SystemExit(f"Katalog meldet einen Fehler: {payload}")
    return payload["result"].get("resources", [])


def describe(value, depth: int = 0) -> str:
    """Kurzbeschreibung des Aufbaus, ohne die ganze Antwort auszugeben."""
    pad = "  " * depth
    if isinstance(value, dict):
        keys = list(value)[:14]
        lines = [f"{pad}Objekt mit {len(value)} Feldern: {', '.join(keys)}"]
        if depth < 2:
            for key in keys[:4]:
                lines.append(describe(value[key], depth + 1))
        return "\n".join(lines)
    if isinstance(value, list):
        lines = [f"{pad}Liste mit {len(value)} Einträgen"]
        if value and depth < 2:
            lines.append(describe(value[0], depth + 1))
        return "\n".join(lines)
    text = str(value)
    return f"{pad}{type(value).__name__}: {text[:70]}"


def inspect(url: str) -> None:
    print(f"  Abruf: {url}")
    try:
        response = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  FEHLER {exc.__class__.__name__}: {exc}")
        return
    kind = response.headers.get("content-type", "?")
    print(f"  HTTP {response.status_code}, {kind}, {len(response.content)} Bytes")
    if response.status_code != 200:
        return
    try:
        data = response.json()
    except ValueError:
        print(f"  Kein JSON. Anfang: {response.text[:180]!r}")
        return
    print(describe(data).replace("\n", "\n  "))
    # Ein vollständiger Beispielsatz sagt mehr als jede Feldliste.
    sample = data
    for _ in range(3):
        if isinstance(sample, dict):
            for key in ("features", "data", "items", "records"):
                if isinstance(sample.get(key), list) and sample[key]:
                    sample = sample[key][0]
                    break
            else:
                break
        elif isinstance(sample, list) and sample:
            sample = sample[0]
        else:
            break
    if sample is not data:
        text = json.dumps(sample, ensure_ascii=False, indent=1)
        print("  Beispielsatz:")
        print("    " + text[:900].replace("\n", "\n    "))


def main() -> int:
    for title, dataset_id in DATASETS.items():
        print(f"=== {title} ({dataset_id}) ===")
        try:
            found = resources(dataset_id)
        except requests.RequestException as exc:
            print(f"Katalog nicht erreichbar: {exc}")
            return 1
        print(f"{len(found)} Ressourcen:\n")
        for res in found:
            name = res.get("name", "?")
            print(f"- {name}  [{res.get('format', '?')}]")
            print(f"  {res.get('url', '')}")
            note = (res.get("description") or "").strip().replace("\n", " ")
            if note:
                print(f"  {note[:220]}")
            print()

        # JSON-Dienste ansehen, seebezogene zuerst.
        def sort_key(res: dict) -> tuple[int, str]:
            name = (res.get("name", "") + " " + (res.get("description") or "")).lower()
            return (0 if any(h in name for h in LAKE_HINTS) else 1, name)

        services = [r for r in found
                    if "json" in (r.get("format", "") or "").lower()
                    and (r.get("url") or "").startswith("http")]
        for res in sorted(services, key=sort_key)[:6]:
            print(f"--- {res.get('name', '?')} ---")
            inspect(res["url"])
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
