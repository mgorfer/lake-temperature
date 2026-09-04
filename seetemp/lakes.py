"""Stammdaten der betrachteten Kärntner Seen.

Die morphometrischen Angaben (Seehöhe, Fläche, maximale Tiefe) sind gerundete,
öffentlich dokumentierte Näherungswerte. Sie dienen zwei Zwecken:

* Beschriftung der Grafiken,
* Parametrisierung des Offline-Demomodells in ``sources/synthetic.py``.

Für die Auswertung echter Messdaten sind sie ohne Bedeutung -- dort zählt
ausschliesslich die in ``config/stations.json`` hinterlegte Stationszuordnung.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lake:
    key: str
    name: str
    altitude_m: int
    area_km2: float
    max_depth_m: int
    lat: float
    lon: float

    @property
    def label(self) -> str:
        return self.name


LAKES: tuple[Lake, ...] = (
    Lake("woerthersee", "Wörthersee", 439, 19.39, 85, 46.622, 14.152),
    Lake("ossiacher_see", "Ossiacher See", 501, 10.50, 52, 46.669, 13.983),
    Lake("millstaetter_see", "Millstätter See", 588, 13.28, 141, 46.797, 13.573),
    Lake("faaker_see", "Faaker See", 554, 2.20, 30, 46.573, 13.913),
    Lake("klopeiner_see", "Klopeiner See", 446, 1.10, 48, 46.617, 14.573),
    Lake("weissensee", "Weißensee", 929, 6.50, 99, 46.716, 13.294),
    Lake("keutschacher_see", "Keutschacher See", 506, 1.32, 16, 46.583, 14.201),
    Lake("laengsee", "Längsee", 548, 0.75, 21, 46.774, 14.443),
    Lake("turnersee", "Turnersee", 465, 0.44, 13, 46.590, 14.531),
    Lake("pressegger_see", "Pressegger See", 558, 0.55, 14, 46.630, 13.400),
    Lake("afritzer_see", "Afritzer See", 750, 0.55, 20, 46.727, 13.803),
    Lake("magdalensee", "Magdalensee", 505, 0.15, 11, 46.640, 13.930),
)

BY_KEY = {lake.key: lake for lake in LAKES}


def resolve(keys: list[str] | None) -> list[Lake]:
    """Wählt Seen anhand ihrer Schlüssel aus; ``None`` liefert alle."""
    if not keys:
        return list(LAKES)
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise SystemExit(
            f"Unbekannte See-Schlüssel: {', '.join(unknown)}\n"
            f"Verfügbar: {', '.join(BY_KEY)}"
        )
    return [BY_KEY[k] for k in keys]
