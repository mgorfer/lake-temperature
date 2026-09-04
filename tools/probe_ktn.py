"""Erkundet den offenen Datensatz des Hydrographischen Dienstes Kärnten.

Die URL des JSON-Dienstes steht nicht im Code, sondern im Katalog von
data.gv.at. Weil der Katalog seinen Unterbau gewechselt hat und die alte
CKAN-Adresse mit 404 antwortet, geht dieses Werkzeug drei Wege nebeneinander
und berichtet, welcher trägt:

1. mehrere bekannte API-Formen,
2. die Katalogseite im HTML, aus der die Ressourcenadressen gelesen werden,
3. die Dokumentations-PDF des JSON-Dienstes im Klartext.

Alles, was dabei nach einem JSON-Dienst aussieht, wird abgerufen und sein
Aufbau beschrieben -- Feldnamen und ein Beispielsatz sagen mehr als jede
Vermutung.

    python tools/probe_ktn.py
"""

from __future__ import annotations

import io
import json
import re
import sys
import time

import requests

DATASET = "bf851ec0-94cb-43ca-83cb-a9dc96ddea51"  # Hydrographische Daten Kärnten
BERICHTE = "8ce097dd-a094-4a89-ad04-83a8c93f5ec8"  # Hydrographie öffentliche Berichte

API_CANDIDATES = [
    "https://www.data.gv.at/katalog/api/3/action/package_show?id={id}",
    "https://www.data.gv.at/api/3/action/package_show?id={id}",
    "https://www.data.gv.at/katalog/api/action/package_show?id={id}",
    "https://www.data.gv.at/api/hub/repo/datasets/{id}",
    "https://www.data.gv.at/api/datasets/{id}",
]
PAGE_CANDIDATES = [
    "https://www.data.gv.at/datasets/{id}?locale=de",
    "https://www.data.gv.at/katalog/dataset/{id}",
]
#: (Verbindung, Antwort). Knapp gehalten: eine Sonde, die hängt, ist wertlos --
#: sie soll berichten, was erreichbar ist, nicht auf Unerreichbares warten.
TIMEOUT = (5, 12)
#: Gesamtbudget. Danach bricht die Sonde ab und gibt aus, was sie hat.
BUDGET_S = 240
_START = time.monotonic()


def budget_left() -> float:
    return BUDGET_S - (time.monotonic() - _START)


def out(text: str = "") -> None:
    """Sofort ausgeben -- sonst steht bei einem Abbruch nichts im Protokoll."""
    print(text, flush=True)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>\\)]+")
#: Adressen, die als Datenschnittstelle in Frage kommen.
INTERESTING = re.compile(r"(ktn\.gv\.at|\.json|\.geojson|\.pdf|arcgis|wfs|ows)", re.I)
BORING = re.compile(r"(w3\.org|schema\.org|creativecommons|data\.gv\.at/(css|js|img|static)"
                    r"|fonts\.|gstatic|googleapis)", re.I)


def get(url: str) -> requests.Response | None:
    if budget_left() <= 0:
        out("  (Zeitbudget aufgebraucht, übersprungen)")
        return None
    try:
        response = requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as exc:
        out(f"  {exc.__class__.__name__}: {exc}")
        return None
    kind = response.headers.get("content-type", "?").split(";")[0]
    out(f"  HTTP {response.status_code}  {kind}  {len(response.content)} Bytes")
    return response


def harvest(text: str) -> list[str]:
    """Sammelt Adressen aus HTML oder JSON, ohne Rahmenwerk-Krempel."""
    found = []
    for url in URL_PATTERN.findall(text):
        url = url.rstrip(".,;)\"'")
        if INTERESTING.search(url) and not BORING.search(url) and url not in found:
            found.append(url)
    return found


def describe(value, depth: int = 0) -> str:
    pad = "  " * depth
    if isinstance(value, dict):
        keys = list(value)[:14]
        lines = [f"{pad}Objekt, {len(value)} Felder: {', '.join(keys)}"]
        if depth < 2:
            lines += [describe(value[k], depth + 1) for k in keys[:4]]
        return "\n".join(lines)
    if isinstance(value, list):
        lines = [f"{pad}Liste, {len(value)} Einträge"]
        if value and depth < 2:
            lines.append(describe(value[0], depth + 1))
        return "\n".join(lines)
    return f"{pad}{type(value).__name__}: {str(value)[:70]}"


def inspect_json(url: str) -> bool:
    out(f"\n--- {url}")
    response = get(url)
    if response is None or response.status_code != 200:
        return False
    if "json" not in response.headers.get("content-type", "").lower():
        out("  kein JSON-Inhaltstyp, übersprungen")
        return False
    try:
        data = response.json()
    except ValueError:
        out(f"  kein JSON, Anfang: {response.text[:150]!r}")
        return False
    out("  " + describe(data).replace("\n", "\n  "))
    sample = data
    for _ in range(3):
        if isinstance(sample, dict):
            for key in ("features", "data", "items", "records", "messstellen", "result"):
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
        out("  Beispielsatz:")
        text = json.dumps(sample, ensure_ascii=False, indent=1)
        out("    " + text[:1200].replace("\n", "\n    "))
    return True


def read_pdf(url: str) -> None:
    """Die Dokumentation nennt die Endpunkte -- also hineinsehen."""
    try:
        from pypdf import PdfReader
    except ImportError:
        out("  (pypdf nicht installiert, PDF wird nicht gelesen)")
        return
    response = get(url)
    if response is None or response.status_code != 200:
        return
    try:
        reader = PdfReader(io.BytesIO(response.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:12])
    except Exception as exc:
        out(f"  PDF nicht lesbar: {exc}")
        return
    out(f"  {len(reader.pages)} Seiten, {len(text)} Zeichen Text")
    urls = harvest(text)
    if urls:
        out("  Adressen in der Dokumentation:")
        for u in urls[:25]:
            out(f"    {u}")
    # Der Fliesstext nennt oft Feldnamen und Beispielaufrufe.
    out("  Auszug:")
    condensed = re.sub(r"\n{2,}", "\n", text).strip()
    out("    " + condensed[:2500].replace("\n", "\n    "))


def main() -> int:
    candidates: list[str] = []

    out("### API-Formen")
    for template in API_CANDIDATES:
        url = template.format(id=DATASET)
        out(f"\n{url}")
        response = get(url)
        if response is not None and response.status_code == 200:
            candidates += harvest(response.text)

    out("\n\n### Katalogseiten")
    for dataset in (DATASET, BERICHTE):
        for template in PAGE_CANDIDATES:
            url = template.format(id=dataset)
            out(f"\n{url}")
            response = get(url)
            if response is not None and response.status_code == 200:
                found = harvest(response.text)
                for item in found[:30]:
                    out(f"    {item}")
                candidates += found

    unique = []
    for url in candidates:
        if url not in unique:
            unique.append(url)

    pdfs = [u for u in unique if u.lower().endswith(".pdf")]
    jsons = [u for u in unique if not u.lower().endswith((".pdf", ".csv", ".zip"))]

    out("\n\n### Dokumentation")
    for url in pdfs[:2]:
        out(f"\n{url}")
        read_pdf(url)

    out("\n\n### Dienste ansehen")
    # Zuerst, was nach einem Dienst des Landes aussieht.
    def rank(url: str) -> tuple[int, int]:
        u = url.lower()
        return (0 if "ktn.gv.at" in u else 1,
                0 if any(k in u for k in ("json", "see", "wasser", "hydro")) else 1)

    jsons.sort(key=rank)
    if not jsons:
        out("Keine Kandidaten gefunden.")
    for url in jsons[:8]:
        if budget_left() <= 0:
            out("(Zeitbudget aufgebraucht)")
            break
        inspect_json(url)
    out(f"\nRestbudget: {budget_left():.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
