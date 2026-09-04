"""Offline-Demoquelle -- erzeugt PLAUSIBLE, aber ERFUNDENE Messreihen.

Warum es das gibt: die App soll auch ohne Netzzugang lauffähig sein und
zeigen, wie die Auswertung aussieht. Die erzeugten Werte sind KEINE Messdaten
und dürfen nicht als solche verwendet oder zitiert werden. Jede aus dieser
Quelle erzeugte Grafik wird sichtbar als Demo gekennzeichnet.

Das Modell ist rein deterministisch (fester Seed) und bildet ab:

* Jahresgang als Grundwelle plus Oberwelle (langsamer Frühjahrsanstieg,
  träges Abkühlen im Herbst),
* Wärmeträgheit tiefer Seen: geringere Sommerspitze, späteres Maximum,
  höheres Wintermittel,
* Höhenabhängigkeit,
* Witterungsrauschen als AR(1)-Prozess plus Jahresoffset,
* einen Erwärmungstrend von rund +0,35 K pro Jahrzehnt.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from ..lakes import Lake
from .base import Dataset

TREND_K_PER_YEAR = 0.035
TREND_BASE_YEAR = 1991


def _params(lake: Lake) -> dict[str, float]:
    """Leitet die Modellparameter aus der Seemorphometrie ab."""
    inertia = math.log1p(lake.max_depth_m) / math.log1p(141.0)  # 0 flach .. 1 tief
    alt = lake.altitude_m - 440
    return {
        "summer": 27.0 - 0.0085 * alt - 3.4 * inertia,
        "winter": 3.0 + 1.9 * inertia - 0.0012 * alt,
        "peak_doy": 199 + 15 * inertia,
        "noise_sd": 1.55 - 0.75 * inertia,
        "inertia": inertia,
    }


def _seasonal(doy: np.ndarray, p: dict[str, float]) -> np.ndarray:
    phase = 2 * np.pi * (doy - p["peak_doy"]) / 365.25
    base = 0.5 * (1 + np.cos(phase))
    # Oberwelle: Frühjahr steigt verhalten, Herbst kühlt verzögert ab.
    skew = 0.085 * np.sin(phase)
    shape = np.clip(base + skew, 0.0, 1.0)
    return p["winter"] + (p["summer"] - p["winter"]) * shape


def generate(lakes: list[Lake], start: date, end: date, seed: int = 20240711) -> Dataset:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    doy = np.asarray(dates.dayofyear, dtype=float)
    years = np.asarray(dates.year)

    rows = []
    for lake in lakes:
        p = _params(lake)
        seasonal = _seasonal(doy, p)

        # AR(1)-Witterungsrauschen, im Sommer kräftiger als unter Eis.
        rho = 0.86
        innov = rng.normal(0.0, p["noise_sd"] * math.sqrt(1 - rho**2), len(dates))
        weather = np.empty(len(dates))
        acc = 0.0
        for i, e in enumerate(innov):
            acc = rho * acc + e
            weather[i] = acc
        weather *= 0.45 + 0.55 * (seasonal - seasonal.min()) / (np.ptp(seasonal) or 1.0)

        # Jahresoffset (kühle/warme Sommer) und Erwärmungstrend.
        offsets = {y: rng.normal(0.0, 0.62) for y in np.unique(years)}
        year_offset = np.array([offsets[y] for y in years])
        trend = TREND_K_PER_YEAR * (years - TREND_BASE_YEAR)

        temp = seasonal + weather + year_offset + trend
        temp = np.clip(temp, 0.0, None)
        rows.append(
            pd.DataFrame({"lake_key": lake.key, "date": dates, "temp_c": np.round(temp, 1)})
        )

    return Dataset(
        frame=pd.concat(rows, ignore_index=True),
        source="Demo-Modell (synthetisch)",
        is_demo=True,
        notes=[
            "Synthetische Werte aus einem Jahresgangmodell -- keine Messdaten.",
            f"Enthaltener Trend: +{TREND_K_PER_YEAR * 10:.2f} K/Jahrzehnt ab {TREND_BASE_YEAR}.",
        ],
    )
