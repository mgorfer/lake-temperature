"""Quelle: aktuelle Seetemperaturen des Landes Kärnten (ArcGIS-REST-Dienst).

Das Land Kärnten veröffentlicht die aktuellen Oberflächentemperaturen der
Badeseen über einen ArcGIS-Feature-Dienst. Dieser liefert immer nur den
jüngsten Messwert je See -- er ergänzt also die Tagesaktualität, ersetzt aber
nicht die lange Reihe aus eHYD.

Dienst-URL und Feldnamen stehen in ``config/stations.json`` unter ``kagis``,
weil beides serverseitig geändert werden kann, ohne dass die App das merkt.
"""

from __future__ import annotations

import pandas as pd
import requests

from .base import Dataset

TIMEOUT = 45


def fetch(config: dict) -> Dataset:
    url = config.get("url")
    if not url:
        raise SystemExit(
            "Kein ArcGIS-Dienst konfiguriert -- bitte config/stations.json "
            "unter \"kagis\" -> \"url\" befüllen."
        )
    fields = config.get("fields", {})
    name_field = fields.get("name", "SEENAME")
    temp_field = fields.get("temperature", "TEMPERATUR")
    date_field = fields.get("date", "MESSDATUM")
    mapping = {k.lower(): v for k, v in config.get("name_to_lake_key", {}).items()}

    params = {"where": "1=1", "outFields": "*", "f": "json", "returnGeometry": "false"}
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise SystemExit(f"ArcGIS-Dienst meldet einen Fehler: {payload['error']}")

    rows, notes = [], []
    for feature in payload.get("features", []):
        attrs = feature.get("attributes", {})
        name = str(attrs.get(name_field, "")).strip()
        lake_key = mapping.get(name.lower())
        if not lake_key:
            notes.append(f"Unzugeordneter See im Dienst: {name!r}")
            continue
        stamp = attrs.get(date_field)
        # ArcGIS liefert Zeitstempel als Millisekunden seit Epoch.
        when = (
            pd.to_datetime(stamp, unit="ms", errors="coerce")
            if isinstance(stamp, (int, float))
            else pd.to_datetime(stamp, errors="coerce")
        )
        rows.append(
            {
                "lake_key": lake_key,
                "date": (when or pd.Timestamp.today()).normalize(),
                "temp_c": pd.to_numeric(attrs.get(temp_field), errors="coerce"),
            }
        )

    if not rows:
        raise SystemExit("ArcGIS-Dienst lieferte keine zuordenbaren Seen.\n  " + "\n  ".join(notes))

    return Dataset(
        frame=pd.DataFrame(rows),
        source="Land Kärnten -- aktuelle Seetemperaturen",
        notes=notes or ["Tagesaktuelle Momentwerte, keine lange Reihe."],
    )
