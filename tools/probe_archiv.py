"""Sucht ein Archiv: Tageswerte des laufenden Jahres statt der letzten 24 h.

Der Abruf des Landesdienstes trägt rund einen Tag. Für "jeder Tag dieses
Jahres" braucht es eine längere Reihe. Ob es sie gibt, steht nicht in der
Datei, die wir kennen -- also wird gefragt, und zwar dort, wo man fragen
kann:

* **data.gv.at** führt den Katalog, in dem das Land seine Dienste anmeldet.
  Zu jedem Datensatz stehen dort die Ressourcen mit ihren Adressen. Der
  Katalog antwortet auch Rechenzentren -- anders als ktn.gv.at selbst.
* **ktn.gv.at** wird trotzdem versucht. Scheitert es hier am Netz, heisst
  das nicht, dass es am Handy scheitert; der Versuch ist protokolliert und
  die Liste der Kandidaten kann von dort wiederholt werden.

Das Skript sucht keine Messwerte, sondern Adressen. Es soll belegen, was
es gibt, statt zu raten.
"""

from __future__ import annotations

import json
import time

import requests

TIMEOUT = (5, 20)
BUDGET_S = 240
_START = time.monotonic()

CKAN = "https://www.data.gv.at/katalog/api/3/action"

#: Datensätze, die die Suche als einschlägig ausgewiesen hat.
DATENSAETZE = [
    "e454bf6a-3321-4a86-998a-af61123eb056",  # Seewasserstände Kärnten
    "bf851ec0-94cb-43ca-83cb-a9dc96ddea51",  # Hydrographische Daten Kärnten
]

SUCHEN = [
    "Kärnten Wassertemperatur",
    "Kärnten hydrographische Daten",
    "Seewasserstände",
]

#: Adressen, die es geben könnte. Die erste ist belegt, die übrigen sind
#: Kandidaten -- abgeleitet aus der bekannten Datei, aus grafik_url und aus
#: dem Aufbau des neuen Portals.
KANDIDATEN = [
    "https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json",
    "https://info.ktn.gv.at/asp/hydro/daten/svg/2900120sw.svg",
    "https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see_archiv.json",
    "https://info.ktn.gv.at/asp/hydro/daten/json/2900120.json",
    "https://hydrographie.ktn.gv.at/",
    "https://hydrographie.ktn.gv.at/gewasser/seen-wassertemperatur",
    "https://hydrographie.ktn.gv.at/api/stations",
    "https://hydrographie.ktn.gv.at/api/station/2900120",
]


def left() -> float:
    return BUDGET_S - (time.monotonic() - _START)


def out(text: str = "") -> None:
    print(text, flush=True)


def get(url: str, **kw):
    if left() <= 0:
        out("  (Budget aufgebraucht)")
        return None
    try:
        r = requests.get(url, timeout=TIMEOUT, **kw)
    except requests.RequestException as exc:
        out(f"  {exc.__class__.__name__}: {str(exc)[:150]}")
        return None
    art = r.headers.get("content-type", "?").split(";")[0]
    out(f"  HTTP {r.status_code}  {art}  {len(r.content)} Bytes")
    return r


def ressourcen(paket: dict) -> None:
    """Die Adressen eines Katalogeintrags -- darum geht es hier."""
    out(f"  Titel:  {paket.get('title', '?')}")
    notes = (paket.get("notes") or "").strip().replace("\n", " ")
    if notes:
        out(f"  Notiz:  {notes[:300]}")
    for res in paket.get("resources", []):
        out(f"    · [{res.get('format', '?'):>8}] {res.get('name', '?')}")
        out(f"      {res.get('url', '?')}")
        beschreibung = (res.get("description") or "").strip().replace("\n", " ")
        if beschreibung:
            out(f"      {beschreibung[:220]}")


def katalog() -> None:
    out("## 1. data.gv.at: was das Land angemeldet hat")
    for kennung in DATENSAETZE:
        out(f"\npackage_show {kennung}")
        r = get(f"{CKAN}/package_show", params={"id": kennung})
        if r is None or r.status_code != 200:
            continue
        try:
            paket = r.json().get("result", {})
        except json.JSONDecodeError:
            out("  keine JSON-Antwort")
            continue
        ressourcen(paket)

    for frage in SUCHEN:
        out(f"\npackage_search {frage!r}")
        r = get(f"{CKAN}/package_search", params={"q": frage, "rows": 8})
        if r is None or r.status_code != 200:
            continue
        try:
            treffer = r.json().get("result", {}).get("results", [])
        except json.JSONDecodeError:
            out("  keine JSON-Antwort")
            continue
        for paket in treffer:
            out(f"  – {paket.get('title', '?')}  ({paket.get('name', '?')})")
            for res in paket.get("resources", [])[:6]:
                out(f"      [{res.get('format', '?')}] {res.get('url', '?')}")


def kandidaten() -> None:
    out("\n\n## 2. ktn.gv.at: Kandidaten, direkt versucht")
    out("(Ein Fehlschlag hier ist kein Urteil -- der Dienst sperrt Rechenzentren.)")
    for url in KANDIDATEN:
        out(f"\n{url}")
        r = get(url)
        if r is None or r.status_code != 200:
            continue
        kopf = r.text[:400].replace("\n", " ")
        out(f"  Anfang: {kopf[:300]}")


def main() -> int:
    out("# Suche nach einer längeren Reihe")
    out(f"(Budget {BUDGET_S} s)\n")
    katalog()
    kandidaten()
    out(f"\nFertig nach {time.monotonic() - _START:.0f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
