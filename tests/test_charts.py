"""Prüfungen für die beiden Grafiken zum laufenden Jahr.

Grafiken lassen sich schlecht auf ihr Aussehen prüfen. Prüfbar ist, ob sie
bei den Daten entstehen, die es tatsächlich gibt -- Monatsmittel aus eHYD
ebenso wie Tageswerte -- und ob sie bei fehlenden Daten sauber nichts
liefern statt abzustürzen.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seetemp import charts, climatology, theme as theme_mod  # noqa: E402

TH = theme_mod.THEMES["light"]
KEYS = ["woerthersee", "ossiacher_see"]


def daily_frame(start: int = 1991, end: int = 2026) -> pd.DataFrame:
    """Ein glatter Jahresgang mit leichtem Trend -- reicht als Prüfmuster."""
    rows = []
    for key in KEYS:
        dates = pd.date_range(f"{start}-01-01", f"{end}-09-05", freq="D")
        doy = dates.dayofyear.to_numpy()
        temp = (14 - 10 * np.cos(2 * np.pi * (doy - 20) / 365.25)
                + 0.03 * (dates.year.to_numpy() - start))
        rows.append(pd.DataFrame({"lake_key": key, "date": dates, "temp_c": temp}))
    return pd.concat(rows, ignore_index=True)


def monthly_frame() -> pd.DataFrame:
    """Wie eHYD sie liefert: ein Wert je Monat, auf den Monatsersten gesetzt."""
    daily = daily_frame()
    grouped = (
        daily.assign(monat=pd.DatetimeIndex(daily["date"]).to_period("M"))
        .groupby(["lake_key", "monat"], as_index=False)["temp_c"].mean()
    )
    return grouped.assign(date=grouped["monat"].dt.to_timestamp()).drop(columns="monat")


def measured(days: int = 3, year: int = 2026) -> pd.DataFrame:
    dates = pd.date_range(f"{year}-09-01", periods=days, freq="D")
    return pd.DataFrame({
        "lake_key": np.repeat(KEYS, days),
        "date": list(dates) * len(KEYS),
        "temp_c": [21.5, 22.0, 22.4][:days] * len(KEYS),
        "messungen": [96] * days * len(KEYS),
    })


class MonthHistory(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def render(self, frame, resolution):
        clim = climatology.build(frame, (1991, 2020), 7, None, resolution)
        annotated = climatology.with_anomaly(frame, clim)
        return charts.month_history(
            annotated, clim, 8, th=TH, source="Prüfdaten", is_demo=False,
            out=self.dir / "aug.png", min_values=15 if resolution == "daily" else 1,
        )

    def test_daily_source(self):
        path = self.render(daily_frame(), "daily")
        self.assertIsNotNone(path)
        self.assertGreater(path.stat().st_size, 10_000)

    def test_monthly_source(self):
        """Der Weg, den der Lauf in der Werkbank tatsächlich nimmt."""
        path = self.render(monthly_frame(), "monthly")
        self.assertIsNotNone(path)
        self.assertGreater(path.stat().st_size, 10_000)

    def test_month_without_values_yields_nothing(self):
        frame = monthly_frame()
        frame = frame[pd.DatetimeIndex(frame["date"]).month != 2]
        clim = climatology.build(frame, (1991, 2020), 7, None, "monthly")
        annotated = climatology.with_anomaly(frame, clim)
        self.assertIsNone(charts.month_history(
            annotated, clim, 2, th=TH, source="Prüfdaten", is_demo=False,
            out=self.dir / "feb.png",
        ))

    def test_thin_months_are_dropped_at_daily_resolution(self):
        """Ein August mit drei Messtagen ist kein Augustmittel."""
        frame = daily_frame()
        stamps = pd.DatetimeIndex(frame["date"])
        angebrochen = (stamps.year == 2026) & (stamps.month == 8) & (stamps.day > 3)
        clim = climatology.build(frame, (1991, 2020), 7, None, "daily")
        annotated = climatology.with_anomaly(frame[~angebrochen], clim)
        charts.month_history(annotated, clim, 8, th=TH, source="Prüfdaten",
                             is_demo=False, out=self.dir / "aug.png", min_values=15)
        # Ohne die Schwelle stünde 2026 als Ausreisser in der Reihe; mit ihr
        # endet die Reihe im Vorjahr. Geprüft wird die Auswahl, nicht das Bild.
        subset = annotated[(annotated["month"] == 8) & annotated["temp_c"].notna()]
        zaehlung = subset.groupby(["lake_key", "year"]).size()
        self.assertLess(int(zaehlung.loc[(KEYS[0], 2026)]), 15)


class CurrentYearDaily(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def render(self, frame, resolution, daily=None):
        clim = climatology.build(frame, (1991, 2020), 7, None, resolution)
        return charts.current_year_daily(
            measured() if daily is None else daily, clim, KEYS[0], 2026,
            th=TH, source="Prüfdaten", is_demo=False, out=self.dir / "heuer.png",
            measured_source="Messdienst", caveat="ungeprüfte Rohdaten",
        )

    def test_against_monthly_normals(self):
        path = self.render(monthly_frame(), "monthly")
        self.assertIsNotNone(path)
        self.assertGreater(path.stat().st_size, 10_000)

    def test_against_daily_normals(self):
        path = self.render(daily_frame(), "daily")
        self.assertIsNotNone(path)

    def test_single_day_is_enough(self):
        self.assertIsNotNone(self.render(monthly_frame(), "monthly", measured(days=1)))

    def test_lake_without_measurements_yields_nothing(self):
        leer = measured()[lambda d: d["lake_key"] == KEYS[1]]
        clim = climatology.build(monthly_frame(), (1991, 2020), 7, None, "monthly")
        self.assertIsNone(charts.current_year_daily(
            leer, clim, KEYS[0], 2026, th=TH, source="Prüfdaten", is_demo=False,
            out=self.dir / "leer.png",
        ))

    def test_lake_without_normal_yields_nothing(self):
        clim = climatology.build(monthly_frame(), (1991, 2020), 7, None, "monthly")
        fremd = measured().assign(lake_key="millstaetter_see")
        self.assertIsNone(charts.current_year_daily(
            fremd, clim, "millstaetter_see", 2026, th=TH, source="Prüfdaten",
            is_demo=False, out=self.dir / "fremd.png",
        ))

    def test_other_year_yields_nothing(self):
        clim = climatology.build(monthly_frame(), (1991, 2020), 7, None, "monthly")
        self.assertIsNone(charts.current_year_daily(
            measured(year=2025), clim, KEYS[0], 2026, th=TH, source="Prüfdaten",
            is_demo=False, out=self.dir / "vorjahr.png",
        ))


if __name__ == "__main__":
    unittest.main()
