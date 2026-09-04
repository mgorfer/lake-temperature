"""Stammdaten der betrachteten Kärntner Seen.

Seehöhe und Lage stammen aus dem Seendienst des Hydrographischen Dienstes
Kärnten (Pegelnullpunkt und Koordinaten der Messstelle). Fläche und maximale
Tiefe sind gerundete, öffentlich dokumentierte Näherungswerte. Sie dienen zwei Zwecken:

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
    Lake("woerthersee", "Wörthersee", 439, 19.39, 85, 46.6342, 14.1380),
    Lake("ossiacher_see", "Ossiacher See", 500, 10.50, 52, 46.6519, 13.9029),
    Lake("millstaetter_see", "Millstätter See", 587, 13.28, 141, 46.8015, 13.5713),
    Lake("faaker_see", "Faaker See", 554, 2.20, 30, 46.5775, 13.9142),
    Lake("klopeiner_see", "Klopeiner See", 445, 1.10, 48, 46.6046, 14.5955),
    Lake("weissensee", "Weißensee", 928, 6.50, 99, 46.7156, 13.2945),
    Lake("keutschacher_see", "Keutschacher See", 505, 1.32, 16, 46.5884, 14.1681),
    Lake("laengsee", "Längsee", 549, 0.75, 21, 46.7856, 14.4197),
    Lake("turnersee", "Turnersee", 479, 0.44, 13, 46.5877, 14.5728),
    Lake("pressegger_see", "Pressegger See", 559, 0.55, 14, 46.6284, 13.4383),
    Lake("afritzer_see", "Afritzer See", 747, 0.55, 20, 46.7389, 13.7733),
    Lake("brennsee", "Feldsee (Brennsee)", 746, 0.66, 26, 46.7726, 13.7476),
    Lake("goesselsdorfer_see", "Gösselsdorfer See", 467, 0.42, 4, 46.5658, 14.6197),
    Lake("maltschacher_see", "Maltschacher See", 591, 0.14, 11, 46.7043, 14.1449),
    Lake("rauschele_see", "Rauschele See", 513, 0.09, 11, 46.5861, 14.2200),
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
