"""Quelle für eigene Messreihen als CSV.

Erwartetes Format (Trennzeichen wird erkannt, Kopfzeile erforderlich)::

    lake_key,date,temp_c
    woerthersee,2024-07-01,24.8
    woerthersee,2024-07-02,25.1

Spaltennamen dürfen auch deutsch sein (``see``, ``datum``, ``temperatur``).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import Dataset

ALIASES = {
    "see": "lake_key",
    "seename": "lake_key",
    "lake": "lake_key",
    "datum": "date",
    "tag": "date",
    "temperatur": "temp_c",
    "wassertemperatur": "temp_c",
    "temp": "temp_c",
    "value": "temp_c",
}


def load(path: str | Path) -> Dataset:
    path = Path(path)
    frame = pd.read_csv(path, sep=None, engine="python", comment="#")
    frame.columns = [ALIASES.get(c.strip().lower(), c.strip().lower()) for c in frame.columns]
    frame["temp_c"] = pd.to_numeric(frame["temp_c"], errors="coerce")
    return Dataset(frame=frame, source=f"CSV: {path.name}")
