"""Gemeinsamer Vertrag für alle Datenquellen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

#: Spalten, die jede Quelle liefern muss.
COLUMNS = ["lake_key", "date", "temp_c"]


@dataclass
class Dataset:
    """Tagesmittel der Oberflächen-Wassertemperatur plus Herkunftsangabe.

    ``frame`` hat genau die Spalten aus :data:`COLUMNS`:

    ==========  ==========================================
    lake_key    Schlüssel aus :mod:`seetemp.lakes`
    date        ``datetime64[ns]``, ein Eintrag je Tag
    temp_c      Wassertemperatur in Grad Celsius (float)
    ==========  ==========================================
    """

    frame: pd.DataFrame
    source: str
    is_demo: bool = False
    #: "daily" oder "monthly" -- steuert, wie der Normalwert gebildet wird.
    resolution: str = "daily"
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.resolution not in ("daily", "monthly"):
            raise ValueError(f"Unbekannte Auflösung: {self.resolution!r}")
        missing = [c for c in COLUMNS if c not in self.frame.columns]
        if missing:
            raise ValueError(f"Quelle {self.source!r}: Spalten fehlen: {missing}")
        # Zusatzspalten (etwa der letzte Momentwert) bleiben erhalten.
        extras = [c for c in self.frame.columns if c not in COLUMNS]
        self.frame = (
            self.frame.loc[:, COLUMNS + extras]
            .assign(date=lambda d: pd.to_datetime(d["date"]))
            .dropna(subset=["temp_c"])
            .sort_values(["lake_key", "date"])
            .reset_index(drop=True)
        )

    @property
    def span(self) -> tuple[date, date]:
        return self.frame["date"].min().date(), self.frame["date"].max().date()

    def lakes(self) -> list[str]:
        return sorted(self.frame["lake_key"].unique())
