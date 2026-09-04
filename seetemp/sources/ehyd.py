"""Quelle: eHYD -- der Zugang zu den hydrographischen Daten Österreichs.

eHYD (`ehyd.gv.at`, Bundesministerium) ist die amtliche Bezugsquelle für die
langen Reihen. Seemessstellen liegen dort im Bereich Oberflächenwasser
(Feld ``owf``, HZB-Nummern 200014--231688); zu einer Messstelle mit
Temperaturaufzeichnung gehört die Datei **WT-Monatsmittel**, also
Monatsmittel der Wassertemperatur über die gesamte Beobachtungsdauer.

Abruf::

    https://ehyd.gv.at/services/MessstellenExtraData/owf?id=<HZB>&file=<n>

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
from dataclasses import dataclass, field

import pandas as pd
import requests

from .base import Dataset

#: Aktueller Pfad. Die ältere Form "/eHYD/MessstellenExtraData/..." findet
#: sich noch in vielen Anleitungen, liefert aber keinen Dateianhang mehr.
DEFAULT_URL_TEMPLATE = "https://ehyd.gv.at/services/MessstellenExtraData/owf?id={hzb}&file={file}"
LEGACY_URL_TEMPLATE = "https://ehyd.gv.at/eHYD/MessstellenExtraData/owf?id={hzb}&file={file}"
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


@dataclass
class Discovery:
    """Was die Dateisuche an einer Messstelle vorgefunden hat.

    Die Unterscheidung ist wichtig: „URL antwortet nicht", „Messstelle
    liefert gar keine Dateien" und „Messstelle führt keine Temperatur" sehen
    im Ergebnis gleich aus, verlangen aber ganz verschiedene Reaktionen.
    """

    reason: str  # ok | http | no-files | no-temperature
    number: int | None = None
    filename: str | None = None
    files: list[str] = field(default_factory=list)
    status: int | None = None

    @property
    def ok(self) -> bool:
        return self.reason == "ok"

    def explain(self, others_worked: bool | None = None) -> str:
        """Warum es nicht geklappt hat.

        ``others_worked`` entscheidet die Deutung von "keine Dateien": hat
        dieselbe URL-Vorlage anderswo funktioniert, liegt es nicht an ihr,
        sondern an der Messstelle. Ohne diese Unterscheidung schickt die
        Meldung auf die falsche Fährte.
        """
        if self.reason == "ok":
            return f"{self.filename} (file={self.number})"
        if self.reason == "http":
            hint = ("Messstelle in eHYD nicht vorhanden" if others_worked
                    else "URL-Vorlage prüfen")
            return f"HTTP {self.status} — {hint}"
        if self.reason == "no-files":
            if others_worked:
                return (f"HTTP {self.status}, aber keine Dateien — die Messstelle "
                        "stellt über eHYD nichts zum Abruf bereit")
            return (f"HTTP {self.status}, aber ohne Dateianhang — vermutlich die "
                    "falsche URL-Vorlage")
        vorhanden = ", ".join(self.files) or "keine"
        return f"keine Temperaturreihe (vorhanden: {vorhanden})"


def _filename(response: requests.Response) -> str | None:
    disposition = response.headers.get("content-disposition")
    if not disposition or "filename=" not in disposition:
        return None
    return disposition.split("filename=")[-1].strip('"; ')


def find_temperature_file(hzb: str, session: requests.Session,
                          url_template: str = DEFAULT_URL_TEMPLATE) -> Discovery:
    """Sucht die Dateinummer der Temperaturreihe einer Messstelle.

    eHYD nummeriert die Dateien einer Messstelle lückenlos ab 1 und nennt den
    Dateinamen im Header ``Content-Disposition``; fehlt der Header, gibt es
    die Nummer nicht.
    """
    found: list[str] = []
    for number in range(1, MAX_FILES + 1):
        response = session.head(
            url_template.format(hzb=hzb, file=number), timeout=TIMEOUT, allow_redirects=True
        )
        status = getattr(response, "status_code", 200)
        name = _filename(response)
        if name is None:
            if number == 1:
                if status >= 400:
                    return Discovery("http", status=status)
                return Discovery("no-files", status=status)
            break
        found.append(name)
        if TEMPERATURE_FILE.search(name):
            return Discovery("ok", number=number, filename=name, files=found, status=status)
    return Discovery("no-temperature", files=found)


def list_files(hzb: str, session: requests.Session,
               url_template: str = DEFAULT_URL_TEMPLATE) -> list[tuple[int, str]]:
    """Alle Dateien einer Messstelle, nicht nur die Temperaturreihe.

    Die Dateisuche bricht beim ersten Treffer ab -- für die Frage, was eHYD
    je Messstelle überhaupt hergibt, braucht es die vollständige Liste.
    """
    found = []
    for number in range(1, MAX_FILES + 1):
        response = session.head(
            url_template.format(hzb=hzb, file=number), timeout=TIMEOUT, allow_redirects=True
        )
        name = _filename(response)
        if name is None:
            break
        found.append((number, name))
    return found


def probe(stations: dict[str, str],
          templates: tuple[str, ...] = (DEFAULT_URL_TEMPLATE, LEGACY_URL_TEMPLATE)) -> str:
    """Fragt eHYD ab und berichtet, was tatsächlich zurückkommt.

    Gedacht für den Fall, dass der Abruf nichts liefert: das Ergebnis sagt,
    ob die URL-Vorlage veraltet ist, ob die Messstelle keine Dateien führt
    oder ob es schlicht keine Temperaturreihe gibt.
    """
    session = requests.Session()
    lines = []
    for template in templates:
        lines.append(f"URL-Vorlage: {template}")
        # Erst alles erheben, dann deuten: ob die Vorlage taugt, zeigt sich
        # erst im Vergleich aller Messstellen.
        results: list[tuple[str, str, Discovery | str]] = []
        for lake_key, hzb in stations.items():
            if not str(hzb).strip():
                continue
            try:
                results.append((lake_key, str(hzb),
                                find_temperature_file(str(hzb).strip(), session, template)))
            except requests.RequestException as exc:
                results.append((lake_key, str(hzb), f"{exc.__class__.__name__}: {exc}"))
        worked = any(isinstance(r, Discovery) and r.ok for _, _, r in results)
        for lake_key, hzb, result in results:
            text = result.explain(worked) if isinstance(result, Discovery) else result
            lines.append(f"  {lake_key:<18} HZB {hzb}: {text}")
        if worked:
            geeignet = sum(1 for _, _, r in results if isinstance(r, Discovery) and r.ok)
            lines.append(f"  -> {geeignet} von {len(results)} mit Temperaturreihe")
        lines.append("")
    return "\n".join(lines)


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
    failures: list[tuple[str, str, Discovery]] = []
    resolutions: set[str] = set()
    session = requests.Session()

    for lake_key, hzb in usable.items():
        try:
            found = find_temperature_file(hzb, session, url_template)
            if not found.ok:
                failures.append((lake_key, hzb, found))
                continue
            number, filename = found.number, found.filename
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

    # Deutung erst, wenn feststeht, ob die Vorlage überhaupt trägt.
    worked = bool(parts)
    notes += [f"{key}: HZB {hzb}: {found.explain(worked)}"
              for key, hzb, found in failures]

    if not parts:
        raise SystemExit(
            "eHYD lieferte für keinen See Daten:\n  " + "\n  ".join(notes)
            + "\n\nWas eHYD tatsächlich antwortet, zeigt:\n"
              "  python -m seetemp --source ehyd --probe"
        )

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
