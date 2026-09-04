"""Quelle: eHYD -- der Zugang zu den hydrographischen Daten Österreichs.

eHYD (`ehyd.gv.at`, Bundesministerium) ist die amtliche Bezugsquelle für die
langen Reihen. Seemessstellen liegen dort im Bereich Oberflächenwasser
(Feld ``owf``, HZB-Nummern 200014--231688); zu einer Messstelle mit
Temperaturaufzeichnung gehört die Datei **WT-Monatsmittel**, also
Monatsmittel der Wassertemperatur über die gesamte Beobachtungsdauer.

Abruf::

    https://ehyd.gv.at/eHYD/MessstellenExtraData/owf?id=<HZB>&file=<n>

Die Dateinummer ``n`` ist je Messstelle verschieden -- welche Dateien es gibt,
hängt vom Messstellentyp ab (Wasserstand, Durchfluss, Feststoffe,
Wassertemperatur in wechselnder Kombination). Deshalb wird sie nicht geraten,
sondern zur Laufzeit ermittelt: eHYD nennt den Dateinamen im Header
``Content-Disposition``, und gesucht wird die Datei, deren Name auf die
Wassertemperatur verweist.

Dateiformat: Kopfblock mit Stammdaten, danach die Zeile ``Werte:``, ab dann
``TT.MM.JJJJ HH:MM:SS;Wert``. Zeichensatz ISO-8859-1, Dezimalkomma,
Lückenkennung ``Lücke``.
"""

from __future__ import annotations

import io
import re

import pandas as pd
import requests

from .base import Dataset

BASE_URL = "https://ehyd.gv.at/eHYD/MessstellenExtraData/owf"
DEFAULT_URL_TEMPLATE = BASE_URL + "?id={hzb}&file={file}"
#: Dateinamen der Temperaturreihen beginnen bei eHYD mit "WT-".
TEMPERATURE_FILE = re.compile(r"(^|[-_ ])WT[-_ ]|wassertemperatur", re.IGNORECASE)
MAX_FILES = 9
TIMEOUT = 60
ENCODING = "ISO-8859-1"


def parse_export(text: str) -> pd.DataFrame:
    """Zerlegt einen eHYD-Export in ``date``/``temp_c``."""
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
    values = frame["value"].astype(str).str.strip().str.replace(",", ".", regex=False)
    frame["temp_c"] = pd.to_numeric(values, errors="coerce")  # "Lücke" wird NaN
    return (
        frame.dropna(subset=["date", "temp_c"])
        .groupby("date", as_index=False)["temp_c"]
        .mean()
    )


def find_temperature_file(hzb: str, session: requests.Session,
                          url_template: str = DEFAULT_URL_TEMPLATE) -> tuple[int, str] | None:
    """Sucht die Dateinummer der Temperaturreihe einer Messstelle.

    eHYD nummeriert die Dateien einer Messstelle lückenlos ab 1; fehlt der
    Header ``Content-Disposition``, gibt es die Nummer nicht (mehr).
    """
    for number in range(1, MAX_FILES + 1):
        response = session.head(
            url_template.format(hzb=hzb, file=number), timeout=TIMEOUT, allow_redirects=True
        )
        disposition = response.headers.get("content-disposition")
        if not disposition:
            return None
        filename = disposition.split("filename=")[-1].strip('"; ')
        if TEMPERATURE_FILE.search(filename):
            return number, filename
    return None


def infer_resolution(dates: pd.Series) -> str:
    """Tages- oder Monatswerte? Am Medianabstand der Zeitstempel erkennbar."""
    if len(dates) < 3:
        return "monthly"
    spacing = dates.sort_values().diff().dt.days.median()
    return "daily" if spacing is not None and spacing <= 3 else "monthly"


def fetch(stations: dict[str, str], url_template: str = DEFAULT_URL_TEMPLATE) -> Dataset:
    """Lädt je See die Wassertemperaturreihe der zugeordneten Messstelle.

    ``stations`` bildet ``lake_key -> HZB-Nummer`` ab. Seen ohne Nummer
    werden übersprungen und in den Notizen vermerkt.
    """
    usable = {k: str(v).strip() for k, v in stations.items() if str(v).strip()}
    if not usable:
        raise SystemExit(
            "Keine eHYD-Messstellen konfiguriert.\n"
            "In config/stations.json unter \"ehyd\".\"stations\" die HZB-Nummern "
            "der gewünschten Seen eintragen (siehe README, Abschnitt Datenquellen)."
        )

    parts: list[pd.DataFrame] = []
    notes: list[str] = []
    resolutions: set[str] = set()
    session = requests.Session()

    for lake_key, hzb in usable.items():
        try:
            found = find_temperature_file(hzb, session, url_template)
            if found is None:
                notes.append(f"{lake_key}: HZB {hzb} führt keine Wassertemperaturreihe")
                continue
            number, filename = found
            response = session.get(
                url_template.format(hzb=hzb, file=number), timeout=TIMEOUT
            )
            response.raise_for_status()
            response.encoding = ENCODING
            series = parse_export(response.text)
        except requests.RequestException as exc:
            notes.append(f"{lake_key}: Abruf fehlgeschlagen ({exc.__class__.__name__}: {exc})")
            continue
        except ValueError as exc:
            notes.append(f"{lake_key}: Export nicht lesbar ({exc})")
            continue

        if series.empty:
            notes.append(f"{lake_key}: {filename} enthielt keine verwertbaren Werte")
            continue

        resolutions.add(infer_resolution(series["date"]))
        parts.append(series.assign(lake_key=lake_key))
        notes.append(
            f"{lake_key}: HZB {hzb}, {filename}, {len(series)} Werte "
            f"({series['date'].min():%m/%Y}–{series['date'].max():%m/%Y})"
        )

    if not parts:
        raise SystemExit("eHYD lieferte für keinen See Daten:\n  " + "\n  ".join(notes))

    # Mischt eine Quelle Auflösungen, ist die gröbere die belastbare.
    resolution = "daily" if resolutions == {"daily"} else "monthly"
    if len(resolutions) > 1:
        notes.append("Gemischte Auflösungen -- ausgewertet wird auf Monatsbasis.")

    return Dataset(
        frame=pd.concat(parts, ignore_index=True),
        source="eHYD — Hydrographischer Dienst Österreich",
        resolution=resolution,
        notes=notes,
    )
