"""Quelle: Hydrographischer Dienst Kärnten -- aktuelle Messwerte.

Der Hydrographische Dienst des Landes Kärnten betreibt rund 250 Messstellen
und stellt die aktuellen Werte für Abfluss, Seen, Niederschlag, Grundwasser
und Quellen als JSON/GeoJSON-Dienst bereit (veröffentlicht über data.gv.at
unter CC-BY 4.0). Das alte Portal ``info.ktn.gv.at`` wurde am 10.06.2021
abgeschaltet; aktuell ist ``hydrographie.ktn.gv.at``.

Diese Quelle liefert nur das jüngste Messfenster -- sie ergänzt eHYD um die
Tagesaktualität, ersetzt es aber nicht: für ein langjähriges Mittel braucht
es die lange Reihe.

Dienst-URL und Feldnamen stehen in ``config/stations.json`` unter ``ktn``.
Beides ist bewusst konfigurierbar statt fest verdrahtet, weil der Dienst
serverseitig geändert werden kann, ohne dass die App das bemerkt.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from .base import Dataset

TIMEOUT = 45


def _records(payload: Any) -> list[dict]:
    """Holt die Datensätze aus GeoJSON, ArcGIS-JSON oder einer schlichten Liste."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    if "error" in payload:
        raise SystemExit(f"Der Dienst meldet einen Fehler: {payload['error']}")
    features = payload.get("features")
    if isinstance(features, list):
        # GeoJSON führt die Sachdaten unter "properties", ArcGIS unter "attributes".
        return [f.get("properties") or f.get("attributes") or {} for f in features]
    for key in ("data", "items", "records", "messstellen"):
        if isinstance(payload.get(key), list):
            return [r for r in payload[key] if isinstance(r, dict)]
    return []


def _timestamp(value: Any) -> pd.Timestamp:
    if isinstance(value, (int, float)):  # ArcGIS: Millisekunden seit Epoch
        stamp = pd.to_datetime(value, unit="ms", errors="coerce")
    else:
        stamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(stamp):
        stamp = pd.Timestamp.today()
    return stamp.tz_localize(None).normalize()


def fetch(config: dict) -> Dataset:
    url = config.get("url")
    if not url:
        raise SystemExit(
            "Kein Dienst konfiguriert -- in config/stations.json unter \"ktn\".\"url\" "
            "die JSON-Adresse des Hydrographischen Dienstes Kärnten eintragen "
            "(siehe README, Abschnitt Datenquellen)."
        )
    fields = config.get("fields", {})
    name_field = fields.get("name", "SEENAME")
    temp_field = fields.get("temperature", "WT")
    date_field = fields.get("date", "MESSDATUM")
    mapping = {k.strip().lower(): v for k, v in config.get("name_to_lake_key", {}).items()}

    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    records = _records(response.json())
    if not records:
        raise SystemExit(f"Der Dienst unter {url} lieferte keine Datensätze.")

    rows, notes = [], []
    for record in records:
        name = str(record.get(name_field, "")).strip()
        lake_key = mapping.get(name.lower())
        if not lake_key:
            notes.append(f"Nicht zugeordnet: {name!r}")
            continue
        value = pd.to_numeric(record.get(temp_field), errors="coerce")
        if pd.isna(value):
            notes.append(f"{lake_key}: kein Temperaturwert im Feld {temp_field!r}")
            continue
        rows.append({
            "lake_key": lake_key,
            "date": _timestamp(record.get(date_field)),
            "temp_c": float(value),
        })

    if not rows:
        raise SystemExit(
            "Der Dienst lieferte keine zuordenbaren Seen. Feldnamen und "
            "Namenszuordnung in config/stations.json prüfen:\n  " + "\n  ".join(notes[:15])
        )

    return Dataset(
        frame=pd.DataFrame(rows),
        source="Hydrographischer Dienst Kärnten — aktuelle Werte",
        notes=notes or ["Tagesaktuelle Werte, keine lange Reihe."],
    )
