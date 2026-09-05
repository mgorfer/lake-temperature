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
import re
import sys
import time
from urllib.parse import quote

import requests

TIMEOUT = (5, 20)
BUDGET_S = 240
_START = time.monotonic()

#: data.gv.at hat den Relaunch hinter sich; die alte CKAN-Adresse antwortet
#: mit 404. Welche Form gilt, wird nicht geraten, sondern durchprobiert.
API_FORMEN = [
    "https://www.data.gv.at/api/hub/search/datasets/{id}",
    "https://www.data.gv.at/api/3/action/package_show?id={id}",
    "https://www.data.gv.at/katalog/api/3/action/package_show?id={id}",
    "https://www.data.gv.at/api/hub/repo/datasets/{id}",
]

SUCH_FORMEN = [
    "https://www.data.gv.at/api/hub/search/search?q={q}&filter=dataset&limit=8",
    "https://www.data.gv.at/api/3/action/package_search?q={q}&rows=8",
]

#: Die Seite selbst -- wenn keine Schnittstelle antwortet, stehen die
#: Adressen der Ressourcen immer noch im HTML.
SEITEN = [
    "https://www.data.gv.at/datasets/{id}?locale=de",
    "https://www.data.gv.at/katalog/dataset/{id}",
]

#: Datensätze, die die Suche als einschlägig ausgewiesen hat.
DATENSAETZE = [
    "e454bf6a-3321-4a86-998a-af61123eb056",  # Seewasserstände Kärnten
    "bf851ec0-94cb-43ca-83cb-a9dc96ddea51",  # Hydrographische Daten Kärnten
]

SUCHEN = ["Kärnten Wassertemperatur", "hydrographische Daten Kärnten"]

#: Was in einer Fundstelle interessant ist: Adressen des Landes und
#: alles, was nach abholbaren Daten aussieht.
INTERESSANT = re.compile(
    r"https?://[^\s\"'<>\\)]*(?:ktn\.gv\.at|\.json|\.csv|\.zip|geojson)[^\s\"'<>\\)]*",
    re.IGNORECASE,
)

#: Adressen, die es geben könnte. Die erste ist belegt, die übrigen sind
#: Kandidaten -- abgeleitet aus der bekannten Datei, aus grafik_url und aus
#: dem Aufbau des neuen Portals.
#: Der Katalogeintrag nennt neben der bekannten Sammeldatei einen Endpunkt
#: **je Messstelle** und eine zweite Fassung mit ``_l``. Was die tragen,
#: entscheidet sich am Inhalt -- hier stehen die Kandidaten, die das Handy
#: durchgeht. 2001056 ist der Wörthersee, 2900120 der Afritzer See.
BEKANNT = "https://info.ktn.gv.at/asp/hydro/daten/json"
KANDIDATEN = [
    f"{BEKANNT}/hdkaernten_see.json",
    f"{BEKANNT}/hdkaernten_see_lite.json",
    f"{BEKANNT}/station/2001056.json",
    f"{BEKANNT}/station/2001056_l.json",
    f"{BEKANNT}/station/2900120.json",
    f"{BEKANNT}/station/2900120_l.json",
    f"{BEKANNT}/station/",
    f"{BEKANNT}/",
    "https://info.ktn.gv.at/asp/hydro/daten/svg/2001056sw.svg",
    "https://hydrographie.ktn.gv.at/gewasser/seen-wassertemperatur",
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


def zeige_funde(text: str, grenze: int = 25) -> int:
    """Adressen aus einer Antwort ziehen -- gleich ob JSON oder HTML."""
    funde, gesehen = [], set()
    for treffer in INTERESSANT.findall(text):
        kurz = treffer.rstrip(".,;")
        if kurz in gesehen:
            continue
        gesehen.add(kurz)
        funde.append(kurz)
    for adresse in funde[:grenze]:
        out(f"    → {adresse}")
    if len(funde) > grenze:
        out(f"    … und {len(funde) - grenze} weitere")
    if not funde:
        out("    (keine Adressen in der Antwort)")
    return len(funde)


def katalog() -> None:
    out("## 1. data.gv.at: was das Land angemeldet hat")
    for kennung in DATENSAETZE:
        out(f"\n### Datensatz {kennung}")
        for form in API_FORMEN + SEITEN:
            url = form.format(id=kennung)
            out(f"\n{url}")
            r = get(url)
            if r is None or r.status_code != 200:
                continue
            # Ein Titel hilft beim Einordnen, ist aber nicht der Zweck.
            titel = re.search(r"<title>(.*?)</title>", r.text, re.S)
            if titel:
                out(f"    Titel: {titel.group(1).strip()[:120]}")
            zeige_funde(r.text)

    for frage in SUCHEN:
        out(f"\n### Suche {frage!r}")
        for form in SUCH_FORMEN:
            url = form.format(q=quote(frage))
            out(f"\n{url}")
            r = get(url)
            if r is None or r.status_code != 200:
                continue
            for name in re.findall(r'"(?:title|name)"\s*:\s*"([^"]{4,90})"', r.text)[:10]:
                out(f"    · {name}")
            zeige_funde(r.text, grenze=15)


def beschreibungen() -> None:
    """Der Katalogeintrag im Volltext -- dort steht, was ein Endpunkt trägt.

    Die Adressen allein sagen nichts über den Zeitraum. Ob
    ``station/<id>.json`` einen Tag oder ein Jahr führt und wofür die
    Fassung mit ``_l`` steht, gehört in die Beschreibung der Ressource --
    also wird sie gelesen, statt an den Adressen herumzuraten.
    """
    out("\n\n## 1b. Der Eintrag im Volltext")
    # Nach "hdkaernten" zu suchen bringt nichts -- der Katalog indiziert die
    # Adressen nicht, nur den beschreibenden Text. Also dieselbe Anfrage,
    # die die Adressen zutage gefördert hat, und dann selbst darin suchen.
    url = ("https://www.data.gv.at/api/hub/search/search"
           "?q=" + quote("hydrographische Daten Kärnten")
           + "&filter=dataset&limit=8")
    out(f"\n{url}")
    r = get(url)
    if r is None or r.status_code != 200:
        return
    try:
        daten = r.json()
    except ValueError:
        out("  keine JSON-Antwort")
        return

    # Nicht raten, wie der Katalog seine Felder nennt: die kleinste
    # Struktur suchen, die eine hdkaernten-Adresse noch enthält, und sie
    # mit allen Feldern zeigen.
    #
    # Wichtig: Adressen stehen hier oft als Zeichenketten *in Listen*
    # ("accessURL": [...]). Wer nur in Dicts absteigt, läuft daran vorbei
    # und meldet null Treffer, obwohl die Adresse im Text steht. Listen
    # zählen deshalb zum Inhalt ihres Dicts; abgestiegen wird nur in
    # Dicts -- auch in die, die in Listen liegen.
    treffer: list[dict] = []

    def enthaelt(knoten) -> bool:
        return "hdkaernten" in json.dumps(knoten, ensure_ascii=False)

    def geh(knoten) -> None:
        if not isinstance(knoten, dict):
            return
        unter = [v for v in knoten.values() if isinstance(v, dict)]
        unter += [e for v in knoten.values() if isinstance(v, list)
                  for e in v if isinstance(e, dict)]
        if enthaelt(knoten) and not any(enthaelt(u) for u in unter):
            treffer.append(knoten)
        for kind in unter:
            geh(kind)

    if isinstance(daten, dict):
        geh(daten)
    elif isinstance(daten, list):
        for kind in daten:
            geh(kind)

    out(f"  {len(treffer)} Stellen erwähnen hdkaernten")
    for knoten in treffer[:16]:
        out("")
        for schluessel, wert in knoten.items():
            text = wert if isinstance(wert, str) else json.dumps(wert, ensure_ascii=False)
            text = " ".join(text.split())
            if len(text) > 600:
                text = text[:600] + " …"
            out(f"    {schluessel}: {text}")


def kandidaten(alle: bool = False) -> None:
    out("\n\n## 2. ktn.gv.at: Kandidaten, direkt versucht")
    out("(Ein Fehlschlag hier ist kein Urteil -- der Dienst sperrt Rechenzentren.")
    out(" Vom Handy aus mit --ktn dieselbe Liste vollständig durchgehen.)")
    liste = KANDIDATEN if alle else KANDIDATEN[:1]
    for url in liste:
        out(f"\n{url}")
        r = get(url)
        if r is None or r.status_code != 200:
            continue
        zeitraum(r)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out("# Suche nach einer längeren Reihe")
    out(f"(Budget {BUDGET_S} s)\n")
    if "--nur-ktn" not in argv:
        katalog()
        beschreibungen()
    kandidaten(alle="--ktn" in argv or "--nur-ktn" in argv)
    out(f"\nFertig nach {time.monotonic() - _START:.0f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
