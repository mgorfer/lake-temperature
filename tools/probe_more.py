"""Sucht weitere Wege an die Daten -- vom Runner aus, wo mehr erreichbar ist.

Zwei Lücken sollen geschlossen werden:

* eHYD liefert die Wassertemperatur nur als Monatsmittel. Gibt es doch
  Tageswerte? Dafür werden **alle** Dateien einer Messstelle aufgelistet,
  nicht nur die erste Temperaturreihe.
* Der Kärntner Seendienst antwortet Rechenzentren nicht. Kommt man über
  einen Umweg an dieselben Daten -- Archiv, Spiegel, andere Behörde?

Jeder Weg wird einzeln berichtet, mit knappen Zeitlimits und Gesamtbudget.
"""

from __future__ import annotations

import json
import sys
import time

import requests

from seetemp.sources import ehyd

TIMEOUT = (5, 12)
BUDGET_S = 300
_START = time.monotonic()

KTN_JSON = "https://info.ktn.gv.at/asp/hydro/daten/json/hdkaernten_see.json"
#: Ein paar Messstellen, die bei eHYD eine Temperaturreihe führen.
SAMPLE = {"woerthersee": "212985", "millstaetter_see": "212514", "weissensee": "212563"}


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
        out(f"  {exc.__class__.__name__}: {str(exc)[:160]}")
        return None
    out(f"  HTTP {r.status_code}  {r.headers.get('content-type','?').split(';')[0]}  "
        f"{len(r.content)} Bytes")
    return r


# ------------------------------------------------------------------ 1: eHYD

def alle_ehyd_dateien() -> None:
    """Was führt eHYD je Seemessstelle wirklich?"""
    out("## 1. eHYD: vollständige Dateiliste je Messstelle")
    session = requests.Session()
    for key, hzb in SAMPLE.items():
        out(f"\n{key} (HZB {hzb})")
        try:
            for number, name in ehyd.list_files(hzb, session):
                out(f"  file={number}  {name}")
        except requests.RequestException as exc:
            out(f"  {exc.__class__.__name__}: {exc}")


# --------------------------------------------------------------- 2: Archiv

def wayback() -> None:
    """Das Internet-Archiv ist von überall erreichbar -- auch wenn die Quelle es nicht ist."""
    out("\n\n## 2. Wayback Machine: Momentaufnahmen des Kärntner JSON")
    out("\nVerfügbarkeit:")
    r = get("https://archive.org/wayback/available", params={"url": KTN_JSON})
    newest = None
    if r is not None and r.status_code == 200:
        try:
            snap = (r.json().get("archived_snapshots") or {}).get("closest")
        except ValueError:
            snap = None
        if snap:
            newest = snap.get("url")
            out(f"  jüngste Aufnahme: {snap.get('timestamp')}  {newest}")
        else:
            out("  keine Aufnahme verzeichnet")

    out("\nAlle Aufnahmen (CDX):")
    r = get("https://web.archive.org/cdx/search/cdx",
            params={"url": KTN_JSON, "output": "json", "limit": "40", "fl": "timestamp,statuscode"})
    if r is not None and r.status_code == 200 and r.text.strip():
        try:
            rows = r.json()
            out(f"  {max(0, len(rows)-1)} Aufnahmen")
            for row in rows[1:8]:
                out(f"    {row}")
        except ValueError:
            out(f"  unerwartete Antwort: {r.text[:200]!r}")

    if newest:
        out("\nInhalt der jüngsten Aufnahme:")
        r = get(newest)
        if r is not None and r.status_code == 200:
            try:
                data = r.json()
                feats = data.get("features", [])
                out(f"  {len(feats)} Stationen")
                if feats:
                    q = feats[0].get("properties", {})
                    out(f"  Beispiel: {q.get('gewaesser')} — {q.get('letzter_wert_wt')} °C "
                        f"am {q.get('letzter_wert_wt_date')}")
            except ValueError:
                out(f"  kein JSON: {r.text[:150]!r}")


# ------------------------------------------------------------ 3: GeoSphere

def geosphere() -> None:
    """Die Bundesanstalt betreibt eine dokumentierte offene API."""
    out("\n\n## 3. GeoSphere Austria Data Hub")
    r = get("https://dataset.api.hub.geosphere.at/v1/datasets")
    if r is None or r.status_code != 200:
        return
    try:
        data = r.json()
    except ValueError:
        out("  kein JSON")
        return
    keys = list(data) if isinstance(data, dict) else []
    out(f"  {len(keys)} Datensätze")
    treffer = [k for k in keys if any(w in k.lower() for w in ("see", "lake", "wasser", "hydro"))]
    out(f"  mit See/Wasser im Namen: {treffer or 'keine'}")
    for name in keys[:6]:
        out(f"    {name}")


# ------------------------------------------------------- 4: Jahrbuch, Spiegel

def weitere() -> None:
    out("\n\n## 4. Weitere Wege")
    for label, url in [
        ("Hydrographisches Jahrbuch", "https://wasser.umweltbundesamt.at/hydjb/"),
        ("Jahrbuch-Archiv", "https://wasser.gv.at/hydjb/"),
        ("data.gv.at Ressource", "https://www.data.gv.at/katalog/dataset/"
                                 "bf851ec0-94cb-43ca-83cb-a9dc96ddea51"),
        ("Kärnten über r.jina.ai", "https://r.jina.ai/" + KTN_JSON),
    ]:
        out(f"\n{label}: {url}")
        r = get(url)
        if r is not None and r.status_code == 200 and "jina" in url:
            body = r.text.strip()
            out(f"  Anfang: {body[:200]!r}")
            if '"features"' in body or "gewaesser" in body:
                out("  ENTHÄLT DIE SEEDATEN")


def main() -> int:
    for step in (alle_ehyd_dateien, wayback, geosphere, weitere):
        if left() <= 0:
            out("\n(Budget aufgebraucht)")
            break
        step()
    out(f"\nRestbudget: {left():.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
