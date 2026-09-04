"""Quelle: eHYD (Hydrographischer Dienst Österreich).

eHYD stellt für hydrographische Messstellen -- darunter Seemessstellen mit
Wassertemperatur -- Tageswertreihen als CSV-Export bereit. Genau solche langen
Reihen braucht die App für das langjährige Mittel.

Der Zugriff ist bewusst vollständig konfigurierbar: die HZB-Nummern je See und
die URL-Vorlage stehen in ``config/stations.json``. Die dort ausgelieferte
Datei enthält Platzhalter -- die Zuordnung See -> Messstelle muss einmalig im
eHYD-Messstellenverzeichnis nachgeschlagen und eingetragen werden. Ohne
gepflegte Zuordnung meldet diese Quelle das sauber und bricht ab, statt
Nummern zu raten.

Format des Exports (klassisches eHYD-CSV): Kopfblock mit Metadaten, danach
eine Zeile ``Werte:``, ab dann ``TT.MM.JJJJ HH:MM;Wert``. Zeichensatz
ISO-8859-1, Dezimalkomma, Lückenkennung ``Lücke``.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from .base import Dataset

DEFAULT_URL_TEMPLATE = "https://ehyd.gv.at/eHYD/MessstellenExtraData/wt?id={hzb}&file=2"
TIMEOUT = 60


def parse_export(text: str) -> pd.DataFrame:
    """Zerlegt einen eHYD-CSV-Export in ``date``/``temp_c``."""
    marker = text.find("Werte:")
    body = text[text.find("\n", marker) + 1 :] if marker >= 0 else text
    frame = pd.read_csv(
        io.StringIO(body),
        sep=";",
        header=None,
        names=["stamp", "value"],
        usecols=[0, 1],
        engine="python",
        skip_blank_lines=True,
    )
    frame["date"] = pd.to_datetime(
        frame["stamp"].astype(str).str.strip().str.slice(0, 10),
        format="%d.%m.%Y",
        errors="coerce",
    )
    values = (
        frame["value"].astype(str).str.strip().str.replace(",", ".", regex=False)
    )
    frame["temp_c"] = pd.to_numeric(values, errors="coerce")
    return (
        frame.dropna(subset=["date", "temp_c"])
        .groupby("date", as_index=False)["temp_c"]
        .mean()
    )


def fetch(stations: dict[str, str], url_template: str = DEFAULT_URL_TEMPLATE) -> Dataset:
    """Lädt je See eine eHYD-Reihe.

    ``stations`` bildet ``lake_key -> HZB-Nummer`` ab. Einträge ohne Nummer
    werden übersprungen und in den Notizen vermerkt.
    """
    usable = {k: v for k, v in stations.items() if v}
    if not usable:
        raise SystemExit(
            "Keine eHYD-Messstellen konfiguriert.\n"
            "Bitte in config/stations.json unter \"ehyd\" die HZB-Nummern der "
            "gewünschten Seen eintragen (siehe README, Abschnitt Datenquellen)."
        )

    parts: list[pd.DataFrame] = []
    notes: list[str] = []
    session = requests.Session()
    for lake_key, hzb in usable.items():
        url = url_template.format(hzb=hzb)
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            response.encoding = response.encoding or "ISO-8859-1"
            series = parse_export(response.text)
        except Exception as exc:  # Netz-, HTTP- oder Formatfehler
            notes.append(f"{lake_key}: Abruf fehlgeschlagen ({exc.__class__.__name__}: {exc})")
            continue
        if series.empty:
            notes.append(f"{lake_key}: Export enthielt keine verwertbaren Werte")
            continue
        parts.append(series.assign(lake_key=lake_key))
        notes.append(f"{lake_key}: HZB {hzb}, {len(series)} Tageswerte")

    if not parts:
        raise SystemExit("eHYD lieferte für keinen See Daten:\n  " + "\n  ".join(notes))

    return Dataset(
        frame=pd.concat(parts, ignore_index=True),
        source="eHYD -- Hydrographischer Dienst Österreich",
        notes=notes,
    )
