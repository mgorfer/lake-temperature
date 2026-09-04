"""Quelle: Hydrographischer Dienst Kärnten -- aktuelle Seewerte.

Der Dienst liefert GeoJSON mit einer Station je See::

    https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json

Aufbau je ``features[].properties`` (am tatsächlichen Dienst überprüft):

==========================  ===============================================
``gewaesser``               Seename, ohne Ortszusatz
``hzbnr``                   HZB-Nummer der Messstelle -- dieselbe Kennung
                            wie bei eHYD, daher die verlässlichste Zuordnung
``letzter_wert_wt``         jüngster Messwert der Wassertemperatur in °C
``letzter_wert_wt_date``    Zeitstempel dazu, ISO 8601 mit Zeitzone
``werte.wassertemperatur``  Messreihe der letzten rund 24 Stunden,
                            ``{"date": ..., "value": ...}`` im Viertel- bis
                            Halbstundentakt
``hinweis``                 Warnhinweis des Dienstes
``lizenzzitat``             Lizenz (CC-BY-4.0, Land Kärnten)
==========================  ===============================================

Aus der Messreihe wird ein **Tagesmittel der letzten 24 Stunden** gebildet.
Das ist die Grösse, die sich mit einem Tagesnormalwert vergleichen lässt --
der Normalwert ist selbst ein Mittel über einen Tag. Ein einzelner Momentwert
trüge den Tagesgang mit hinein und würde die Abweichung verfälschen. Der
jüngste Einzelwert bleibt als ``temp_latest`` erhalten, denn er beantwortet
die Frage, wie warm es *jetzt* ist.

Die Daten sind laut Dienst ungeprüfte Rohdaten; dieser Hinweis wird
weitergereicht, nicht verschluckt.
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
#: Fenster für das Tagesmittel.
WINDOW_H = 24

NAME_HINTS = ("gewaesser", "seename", "messstelle", "station", "name", "bezeichnung")
TEMP_HINTS = ("letzterwertwt", "wassertemperatur", "wtemp", "temperatur", "temp", "wt")
DATE_HINTS = ("letzterwertwtdate", "messdatum", "zeitpunkt", "datum", "zeit", "stand")

_TRANSLITERATION = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss",
})


def _fold(text: str) -> str:
    """Vergleichsform: kleingeschrieben, umschrieben, ohne Sonderzeichen.

    Deutsche Umschrift vor der Unicode-Zerlegung, sonst würde aus "ö" ein "o"
    und "Wörthersee" fiele nicht mit "Woerthersee" zusammen.
    """
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
    """Holt die Sachdaten aus GeoJSON, ArcGIS-JSON oder einer Liste."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    if "error" in payload:
        raise SystemExit(f"Der Dienst meldet einen Fehler: {payload['error']}")
    features = payload.get("features")
    if isinstance(features, list):
        return [f.get("properties") or f.get("attributes") or f for f in features
                if isinstance(f, dict)]
    for key in ("messstellen", "stationen", "data", "items", "records", "result"):
        if isinstance(payload.get(key), list):
            return [r for r in payload[key] if isinstance(r, dict)]
    if payload and all(isinstance(v, dict) for v in payload.values()):
        return [{"_schluessel": k, **v} for k, v in payload.items()]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).strip().replace(",", "."))
    return float(match.group()) if match else None


#: "2026-09-04T21:00:00+01:00" -- ISO 8601, Jahr zuerst.
_ISO = re.compile(r"^\s*\d{4}-\d{2}-\d{2}")


def _stamp(value: Any) -> pd.Timestamp | None:
    """Zeitstempel als örtliche Wanduhrzeit.

    Zwei Fallen: ``dayfirst=True`` verdreht ISO-Stempel (aus dem 04.09. wird
    der 9. April), und eine Umrechnung nach UTC schöbe nächtliche Messwerte
    auf den Vortag. Der Kalendertag hier ist der Kärntner, also bleibt die
    Wanduhrzeit stehen und die Zeitzone fällt nur weg.
    """
    if isinstance(value, (int, float)):
        stamp = pd.to_datetime(value, unit="ms", errors="coerce")
    else:
        text = str(value)
        stamp = pd.to_datetime(text, errors="coerce", dayfirst=not _ISO.match(text))
    if pd.isna(stamp):
        return None
    return stamp.tz_localize(None) if stamp.tzinfo is not None else stamp


def daily_mean(series: list[dict], hours: int = WINDOW_H) -> tuple[float | None, int]:
    """Mittel der letzten ``hours`` Stunden aus der Messreihe.

    Vergleichbar mit einem Tagesnormalwert, der selbst ein Tagesmittel ist.
    """
    points = []
    for entry in series or []:
        if not isinstance(entry, dict):
            continue
        when, value = _stamp(entry.get("date")), _number(entry.get("value"))
        if when is not None and value is not None:
            points.append((when, value))
    if not points:
        return None, 0
    newest = max(when for when, _ in points)
    window = [v for when, v in points if when >= newest - pd.Timedelta(hours=hours)]
    return (sum(window) / len(window), len(window)) if window else (None, 0)


def _schema_error(sample: dict, missing: list[str]) -> SystemExit:
    text = json.dumps(sample, ensure_ascii=False, indent=1)[:900]
    return SystemExit(
        f"Im Dienst sind die Felder für {', '.join(missing)} nicht erkennbar.\n"
        f"Vorhandene Felder: {', '.join(list(sample)[:25])}\n\n"
        f"Beispielsatz:\n{text}\n\n"
        "Passende Namen in config/stations.json unter \"ktn\".\"fields\" eintragen."
    )


def load(payload: Any, config: dict | None = None) -> Dataset:
    """Wertet eine bereits geladene Antwort aus -- trennbar für Tests."""
    config = config or {}
    fields = config.get("fields") or {}
    by_name = {_fold(k): v for k, v in (config.get("name_to_lake_key") or {}).items()}
    # Die HZB-Nummer ist dieselbe Kennung wie bei eHYD und damit die
    # verlässlichere Zuordnung: sie überlebt jede Umbenennung.
    by_hzb = {str(v).strip(): k for k, v in (config.get("hzb_to_lake_key") or {}).items()
              if str(v).strip()}

    rows_raw = records(payload)
    if not rows_raw:
        raise SystemExit("Der Dienst lieferte keine Datensätze.")

    keys = list(rows_raw[0])
    name_field = fields.get("name") or _pick(keys, NAME_HINTS)
    temp_field = fields.get("temperature") or _pick(keys, TEMP_HINTS)
    date_field = fields.get("date") or _pick(keys, DATE_HINTS)
    missing = [label for label, field in
               (("den Seenamen", name_field), ("die Temperatur", temp_field))
               if not field]
    if missing:
        raise _schema_error(rows_raw[0], missing)

    rows: list[dict] = []
    notes = [f"Felder: Name={name_field!r}, Temperatur={temp_field!r}, Zeit={date_field!r}"]
    warnings, licences, unmapped = set(), set(), []

    for record in rows_raw:
        name = str(record.get(name_field, "")).strip()
        hzb = record.get("hzbnr")
        lake_key = by_hzb.get(str(hzb).strip()) if hzb is not None else None
        lake_key = lake_key or by_name.get(_fold(name))
        if not lake_key:
            unmapped.append(name or f"HZB {hzb}")
            continue

        latest = _number(record.get(temp_field))
        when = _stamp(record.get(date_field)) if date_field else None
        series = (record.get("werte") or {}).get("wassertemperatur")
        mean, count = daily_mean(series)
        if mean is None and latest is None:
            notes.append(f"{lake_key}: kein Temperaturwert")
            continue

        if record.get("hinweis"):
            warnings.add(str(record["hinweis"]).strip())
        if record.get("lizenzzitat"):
            licences.add(str(record["lizenzzitat"]).strip())

        rows.append({
            "lake_key": lake_key,
            # Tagesmittel, wo vorhanden -- nur das ist mit dem Normalwert vergleichbar.
            "temp_c": round(mean if mean is not None else latest, 2),
            "date": (when or pd.Timestamp.today()).normalize(),
            "temp_latest": latest,
            "latest_at": when,
            "readings": count,
        })

    if not rows:
        raise SystemExit(
            "Kein See liess sich zuordnen. Im Dienst enthalten:\n  "
            + "\n  ".join(sorted(set(unmapped))[:25])
            + "\n\nZuordnung in config/stations.json unter \"ktn\"."
        )

    if unmapped:
        notes.append(f"Ohne Zuordnung übersprungen: {', '.join(sorted(set(unmapped)))}")
    notes += sorted(warnings) + sorted(licences)

    frame = pd.DataFrame(rows).sort_values("date").groupby("lake_key", as_index=False).last()
    return Dataset(frame=frame, source="Hydrographischer Dienst Kärnten — aktuelle Werte",
                   notes=notes)


def fetch(config: dict | None = None) -> Dataset:
    config = config or {}
    url = config.get("url") or DEFAULT_URL
    # Beide Protokolle: ein Zeitablauf auf 443 kann auch heissen, dass der
    # Dienst nur auf 80 hört.
    attempts = [url]
    if url.startswith("https://"):
        attempts.append("http://" + url[len("https://"):])

    problems = []
    for attempt in attempts:
        try:
            response = requests.get(attempt, timeout=TIMEOUT)
            response.raise_for_status()
            return load(response.json(), config)
        except requests.RequestException as exc:
            problems.append(f"{attempt}: {exc.__class__.__name__}: {exc}")
        except ValueError as exc:
            problems.append(f"{attempt}: kein JSON ({exc})")

    raise SystemExit(
        "Der Dienst des Landes Kärnten ist nicht erreichbar:\n  "
        + "\n  ".join(problems)
        + "\n\nAus Rechenzentren heraus (etwa GitHub Actions) antwortet er nicht; "
          "aus einem österreichischen Anschluss in der Regel schon. Zum Prüfen:\n"
          f"  curl -sS -o /dev/null -w '%{{http_code}}\\n' {attempts[0]}"
    )
