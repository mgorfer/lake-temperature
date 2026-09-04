"""Quelle: Hydrographischer Dienst Kärnten -- aktuelle Messwerte.

Der Hydrographische Dienst des Landes betreibt rund 250 Messstellen und
veröffentlicht die aktuellen Werte als JSON, gelistet im Datensatz
"Hydrographische Daten Kärnten" auf data.gv.at (CC-BY 4.0). Die Adresse des
Seendienstes stammt aus diesem Katalog, nicht aus einer Vermutung::

    https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json

Diese Quelle liefert den jüngsten Messwert je See -- sie ergänzt eHYD um die
Tagesaktualität, ersetzt es aber nicht: für ein langjähriges Mittel braucht
es die lange Reihe.

Das Feldschema ist nicht dokumentiert und liess sich beim Bau nicht abrufen
(der Dienst antwortet Rechenzentrums-Adressen nicht). Deshalb rät dieser
Adapter nicht: er erkennt die Felder an ihren Namen, und findet er sie
nicht, nennt er die tatsächlich vorhandenen Felder samt Beispielsatz, statt
mit einer nichtssagenden Meldung abzubrechen. Feste Namen lassen sich in
``config/stations.json`` unter ``ktn.fields`` hinterlegen.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

import pandas as pd
import requests

from .base import Dataset

DEFAULT_URL = "https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json"
TIMEOUT = (10, 30)

#: Wonach die Felderkennung sucht, in dieser Reihenfolge.
NAME_HINTS = ("seename", "gewaesser", "messstelle", "station", "name", "bezeichnung")
TEMP_HINTS = ("wassertemperatur", "wtemp", "temperatur", "temp", "wt")
DATE_HINTS = ("messdatum", "zeitpunkt", "datum", "zeit", "timestamp", "stand")


#: Deutsche Umschrift, damit "Wörthersee" und "Woerthersee" zusammenfallen.
#: Die blosse Unicode-Zerlegung macht aus "ö" ein "o" und würde die beiden
#: Schreibweisen auseinanderhalten.
_TRANSLITERATION = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss",
})


def _fold(text: str) -> str:
    """Vergleichsform: kleingeschrieben, umschrieben, ohne Sonderzeichen."""
    plain = str(text).lower().translate(_TRANSLITERATION)
    plain = unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain)


def _pick(keys: list[str], hints: tuple[str, ...]) -> str | None:
    folded = {k: _fold(k) for k in keys}
    for hint in hints:
        for key, plain in folded.items():
            if plain == hint:
                return key
    for hint in hints:
        for key, plain in folded.items():
            if hint in plain:
                return key
    return None


def records(payload: Any) -> list[dict]:
    """Holt die Datensätze aus GeoJSON, ArcGIS-JSON oder einer Liste."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    if "error" in payload:
        raise SystemExit(f"Der Dienst meldet einen Fehler: {payload['error']}")
    features = payload.get("features")
    if isinstance(features, list):
        # GeoJSON führt die Sachdaten unter "properties", ArcGIS unter "attributes".
        return [f.get("properties") or f.get("attributes") or f for f in features
                if isinstance(f, dict)]
    for key in ("messstellen", "stationen", "data", "items", "records", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    # Manche Dienste liefern ein Objekt je Messstelle, mit der Nummer als Schlüssel.
    if payload and all(isinstance(v, dict) for v in payload.values()):
        return [{"_schluessel": k, **v} for k, v in payload.items()]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _timestamp(value: Any) -> pd.Timestamp:
    if isinstance(value, (int, float)):  # ArcGIS: Millisekunden seit Epoch
        stamp = pd.to_datetime(value, unit="ms", errors="coerce")
    else:
        stamp = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(stamp):
        stamp = pd.Timestamp.today()
    if stamp.tzinfo is not None:
        stamp = stamp.tz_localize(None)
    return stamp.normalize()


def _schema_error(sample: dict, missing: list[str]) -> SystemExit:
    """Sagt, was fehlt und was stattdessen da ist -- nicht bloss, dass es fehlt."""
    text = json.dumps(sample, ensure_ascii=False, indent=1)[:900]
    return SystemExit(
        f"Im Dienst sind die Felder für {', '.join(missing)} nicht erkennbar.\n"
        f"Vorhandene Felder: {', '.join(list(sample)[:25])}\n\n"
        f"Beispielsatz:\n{text}\n\n"
        "Passende Namen in config/stations.json unter \"ktn\".\"fields\" eintragen."
    )


def fetch(config: dict | None = None) -> Dataset:
    config = config or {}
    url = config.get("url") or DEFAULT_URL
    fields = config.get("fields") or {}
    mapping = {_fold(k): v for k, v in (config.get("name_to_lake_key") or {}).items()}

    # Beide Protokolle: ein Zeitablauf auf 443 kann auch heissen, dass der
    # Dienst nur auf 80 hört.
    attempts = [url]
    if url.startswith("https://"):
        attempts.append("http://" + url[len("https://"):])
    problems = []
    payload = None
    for attempt in attempts:
        try:
            response = requests.get(attempt, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            url = attempt
            break
        except requests.RequestException as exc:
            problems.append(f"{attempt}: {exc.__class__.__name__}: {exc}")
        except ValueError as exc:
            problems.append(f"{attempt}: kein JSON ({exc})")
    if payload is None:
        raise SystemExit(
            "Der Dienst des Landes Kärnten ist nicht erreichbar:\n  "
            + "\n  ".join(problems)
            + "\n\nAus Rechenzentren heraus (etwa GitHub Actions) antwortet er nicht; "
              "aus einem österreichischen Anschluss in der Regel schon. Zum Prüfen:\n"
              f"  curl -sS -o /dev/null -w '%{{http_code}}\\n' {attempts[0]}"
        )

    rows_raw = records(payload)
    if not rows_raw:
        raise SystemExit(f"Der Dienst unter {url} lieferte keine Datensätze.")

    keys = list(rows_raw[0])
    name_field = fields.get("name") or _pick(keys, NAME_HINTS)
    temp_field = fields.get("temperature") or _pick(keys, TEMP_HINTS)
    date_field = fields.get("date") or _pick(keys, DATE_HINTS)
    missing = [label for label, field in
               (("den Seenamen", name_field), ("die Temperatur", temp_field))
               if not field]
    if missing:
        raise _schema_error(rows_raw[0], missing)

    rows, notes = [], [f"Felder erkannt: Name={name_field!r}, Temperatur={temp_field!r}, "
                       f"Zeit={date_field!r}"]
    for record in rows_raw:
        name = str(record.get(name_field, "")).strip()
        lake_key = mapping.get(_fold(name))
        if not lake_key:
            notes.append(f"Nicht zugeordnet: {name!r}")
            continue
        value = _number(record.get(temp_field))
        if value is None:
            notes.append(f"{lake_key}: kein Temperaturwert in {temp_field!r}")
            continue
        rows.append({
            "lake_key": lake_key,
            "date": _timestamp(record.get(date_field) if date_field else None),
            "temp_c": value,
        })

    if not rows:
        raise SystemExit(
            "Kein See liess sich zuordnen. Namen im Dienst:\n  "
            + "\n  ".join(sorted({str(r.get(name_field, "")) for r in rows_raw})[:25])
            + "\n\nZuordnung in config/stations.json unter \"ktn\".\"name_to_lake_key\"."
        )

    frame = pd.DataFrame(rows)
    # Je See nur den jüngsten Wert behalten.
    frame = frame.sort_values("date").groupby("lake_key", as_index=False).last()
    return Dataset(
        frame=frame,
        source="Hydrographischer Dienst Kärnten — aktuelle Werte",
        notes=notes,
    )
