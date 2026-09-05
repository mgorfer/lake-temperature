"""Prüfungen der Auswertungslogik (ohne Netz, ohne Grafik)."""

from __future__ import annotations

import unittest
from datetime import date

import numpy as np
import pandas as pd

from seetemp import climatology
from seetemp.lakes import BY_KEY
from seetemp.sources import synthetic
from seetemp.sources.ehyd import parse_export


def constant_series(value: float, start="1991-01-01", end="2020-12-31") -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    return pd.DataFrame({"lake_key": "woerthersee", "date": dates, "temp_c": value})


class DayNumberTest(unittest.TestCase):
    def test_leap_year_alignment(self):
        frame = pd.DataFrame({
            "lake_key": "x",
            "date": pd.to_datetime(["2020-02-28", "2020-02-29", "2020-03-01",
                                    "2021-02-28", "2021-03-01"]),
            "temp_c": 1.0,
        })
        doy = climatology.add_daynumber(frame)["doy"].tolist()
        # 29.02. fällt mit dem 28.02. zusammen, der 1. März ist in beiden Jahren Tag 60.
        self.assertEqual(doy, [59, 59, 60, 59, 60])

    def test_last_day_is_365(self):
        frame = pd.DataFrame({
            "lake_key": "x",
            "date": pd.to_datetime(["2020-12-31", "2021-12-31"]),
            "temp_c": 1.0,
        })
        self.assertEqual(climatology.add_daynumber(frame)["doy"].tolist(), [365, 365])


class ClimatologyTest(unittest.TestCase):
    def test_constant_series_has_zero_spread(self):
        clim = climatology.build(constant_series(12.5))
        self.assertEqual(len(clim.table), 365)
        np.testing.assert_allclose(clim.table["mean"], 12.5)
        np.testing.assert_allclose(clim.table["sd"], 0.0)
        self.assertTrue((clim.table["n"] >= 15 * 30 - 30).all())

    def test_anomaly_is_difference_to_normal(self):
        clim = climatology.build(constant_series(12.5))
        later = constant_series(14.0, "2024-01-01", "2024-12-31")
        annotated = climatology.with_anomaly(later, clim)
        np.testing.assert_allclose(annotated["anomaly"].to_numpy(), 1.5)

    def test_reference_outside_range_is_reported(self):
        with self.assertRaises(SystemExit):
            climatology.build(constant_series(12.5), reference=(2050, 2060))

    def test_window_is_circular_across_the_turn_of_the_year(self):
        # Ein Sägezahn: nur so lässt sich prüfen, dass Tag 1 auch auf Tag 365 zugreift.
        frame = constant_series(0.0)
        frame["temp_c"] = np.where(
            climatology.add_daynumber(frame)["doy"] > 182, 20.0, 10.0
        )
        clim = climatology.build(frame, window=7)
        row = clim.table[clim.table["doy"] == 1].iloc[0]
        self.assertGreater(row["mean"], 10.0)  # Werte aus dem Dezember fliessen ein
        self.assertLess(row["mean"], 20.0)


class SwimDaysTest(unittest.TestCase):
    def test_partial_year_is_compared_on_the_same_calendar_window(self):
        warm = constant_series(25.0, "1991-01-01", "2021-06-30")
        clim = climatology.build(warm.iloc[: 365 * 30])
        annotated = climatology.with_anomaly(warm, clim)
        full = climatology.swim_days(annotated, threshold=22.0)
        partial = climatology.swim_days(annotated, threshold=22.0, through_doy=180)
        # Ohne Beschneidung fällt 2021 heraus, mit Beschneidung ist es vergleichbar.
        self.assertNotIn(2021, full["year"].tolist())
        self.assertIn(2021, partial["year"].tolist())
        # 180 Kalendertage, in Schaltjahren 181 (der 29.02. teilt sich den Tagesindex).
        self.assertTrue(partial["warm"].isin([180, 181]).all())


class SyntheticTest(unittest.TestCase):
    def test_shape_is_seasonal_and_plausible(self):
        data = synthetic.generate([BY_KEY["woerthersee"]], date(2000, 1, 1), date(2010, 12, 31))
        self.assertTrue(data.is_demo)
        frame = climatology.add_daynumber(data.frame)
        july = frame[frame["date"].dt.month == 7]["temp_c"].mean()
        january = frame[frame["date"].dt.month == 1]["temp_c"].mean()
        self.assertGreater(july, january + 10)
        self.assertGreaterEqual(frame["temp_c"].min(), 0.0)
        self.assertLess(frame["temp_c"].max(), 32.0)

    def test_is_reproducible(self):
        args = ([BY_KEY["faaker_see"]], date(2000, 1, 1), date(2001, 12, 31))
        first = synthetic.generate(*args).frame["temp_c"].to_numpy()
        second = synthetic.generate(*args).frame["temp_c"].to_numpy()
        np.testing.assert_array_equal(first, second)


class EhydParserTest(unittest.TestCase):
    SAMPLE = (
        "Messstelle: Musterstelle\n"
        "Werte:\n"
        "01.07.2019 07:00;18,4\n"
        "02.07.2019 07:00;19,1\n"
        "03.07.2019 07:00;Lücke\n"
    )

    def test_reads_comma_decimals_and_skips_gaps(self):
        frame = parse_export(self.SAMPLE)
        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(frame["temp_c"].iloc[0], 18.4)
        self.assertEqual(frame["date"].iloc[1], pd.Timestamp("2019-07-02"))


if __name__ == "__main__":
    unittest.main()


class MonthlyClimatologyTest(unittest.TestCase):
    def monthly_series(self, offset=0.0, start=1991, end=2020) -> pd.DataFrame:
        dates = pd.date_range(f"{start}-01-01", f"{end}-12-01", freq="MS")
        month = pd.DatetimeIndex(dates).month
        return pd.DataFrame({
            "lake_key": "woerthersee",
            "date": dates,
            "temp_c": 12.0 + 8.0 * np.cos((month - 8) / 12 * 2 * np.pi) + offset,
        })

    def test_twelve_support_points_per_lake(self):
        clim = climatology.build(self.monthly_series(), resolution="monthly")
        self.assertEqual(clim.key, "month")
        self.assertEqual(len(clim.table), 12)
        self.assertEqual(clim.table["month"].tolist(), list(range(1, 13)))
        self.assertEqual(clim.method, "Monatsmittel")

    def test_anomaly_against_monthly_normal(self):
        clim = climatology.build(self.monthly_series(), resolution="monthly")
        later = self.monthly_series(offset=2.0, start=2024, end=2024)
        annotated = climatology.with_anomaly(later, clim)
        np.testing.assert_allclose(annotated["anomaly"].to_numpy(), 2.0, atol=1e-9)

    def test_rejects_unknown_resolution(self):
        with self.assertRaises(ValueError):
            climatology.build(self.monthly_series(), resolution="hourly")


class EhydDiscoveryTest(unittest.TestCase):
    """Die Dateinummer der Temperaturreihe wird ermittelt, nicht geraten."""

    class FakeSession:
        def __init__(self, filenames):
            self.filenames = filenames
            self.calls = 0

        def head(self, url, **kwargs):
            self.calls += 1
            number = int(url.split("file=")[1])
            headers = {}
            if number <= len(self.filenames):
                headers["content-disposition"] = (
                    f'attachment; filename={self.filenames[number - 1]}'
                )
            return type("R", (), {"headers": headers, "status_code": self.status})()

        status = 200

    def test_picks_the_water_temperature_file(self):
        from seetemp.sources import ehyd

        session = self.FakeSession([
            "Stammdaten-212985.txt",
            "W-Tagesmittel-212985.csv",
            "W-Monatsmaxima-212985.csv",
            "WT-Monatsmittel-212985.csv",
        ])
        found = ehyd.find_temperature_file("212985", session)
        self.assertTrue(found.ok)
        self.assertEqual((found.number, found.filename), (4, "WT-Monatsmittel-212985.csv"))

    def test_station_without_temperature_series(self):
        from seetemp.sources import ehyd

        session = self.FakeSession(["Stammdaten-212522.txt", "Q-Tagesmittel-212522.csv"])
        found = ehyd.find_temperature_file("212522", session)
        self.assertFalse(found.ok)
        self.assertEqual(found.reason, "no-temperature")
        self.assertIn("Q-Tagesmittel-212522.csv", found.explain())

    def test_a_dead_url_is_not_reported_as_a_missing_series(self):
        """Der Unterschied, der beim ersten CI-Lauf gefehlt hat."""
        from seetemp.sources import ehyd

        gone = self.FakeSession([])
        gone.status = 404
        found = ehyd.find_temperature_file("212985", gone)
        self.assertEqual(found.reason, "http")
        self.assertIn("URL-Vorlage", found.explain())

        empty = self.FakeSession([])  # HTTP 200, aber ohne Dateianhang
        found = ehyd.find_temperature_file("212985", empty)
        self.assertEqual(found.reason, "no-files")
        self.assertIn("URL-Vorlage", found.explain())

    def test_diagnosis_depends_on_whether_the_template_worked_elsewhere(self):
        """Sonst schickt die Meldung auf die falsche Fährte.

        Vier Kärntner Messstellen antworten mit HTTP 200 ohne Dateien,
        während dieselbe Vorlage neun andere einwandfrei bedient. "Falsche
        URL-Vorlage" wäre dann schlicht verkehrt.
        """
        from seetemp.sources.ehyd import Discovery

        leer = Discovery("no-files", status=200)
        self.assertIn("URL-Vorlage", leer.explain(others_worked=False))
        self.assertNotIn("URL-Vorlage", leer.explain(others_worked=True))
        self.assertIn("Messstelle", leer.explain(others_worked=True))

        fehlt = Discovery("http", status=404)
        self.assertIn("URL-Vorlage", fehlt.explain(others_worked=False))
        self.assertIn("nicht vorhanden", fehlt.explain(others_worked=True))

    def test_default_url_uses_the_current_path(self):
        from seetemp.sources import ehyd

        self.assertIn("/services/MessstellenExtraData/owf", ehyd.DEFAULT_URL_TEMPLATE)
        self.assertIn("/eHYD/MessstellenExtraData/owf", ehyd.LEGACY_URL_TEMPLATE)

    def test_resolution_is_inferred_from_the_spacing(self):
        from seetemp.sources import ehyd

        daily = pd.Series(pd.date_range("2020-01-01", periods=40, freq="D"))
        monthly = pd.Series(pd.date_range("2020-01-01", periods=40, freq="MS"))
        self.assertEqual(ehyd.infer_resolution(daily), "daily")
        self.assertEqual(ehyd.infer_resolution(monthly), "monthly")


class CoverageTest(unittest.TestCase):
    """Ein Normalwert aus zwölf Jahren ist keiner aus dreissig -- das muss
    aus der Auswertung hervorgehen, nicht in der Zahl verschwinden."""

    def series(self, lake: str, first_year: int) -> pd.DataFrame:
        dates = pd.date_range(f"{first_year}-01-01", "2020-12-31", freq="D")
        return pd.DataFrame({"lake_key": lake, "date": dates, "temp_c": 12.0})

    def setUp(self):
        frame = pd.concat([self.series("lang", 1991), self.series("kurz", 2009)],
                          ignore_index=True)
        self.clim = climatology.build(frame)

    def test_counts_the_years_behind_each_normal(self):
        self.assertEqual(self.clim.years("lang"), 30)
        self.assertEqual(self.clim.years("kurz"), 12)

    def test_describes_the_span(self):
        self.assertEqual(self.clim.describe_coverage("lang"), "aus 30 Jahren (1991–2020)")
        self.assertEqual(self.clim.describe_coverage("kurz"), "aus 12 Jahren (2009–2020)")

    def test_names_the_thinly_covered_lakes(self):
        self.assertEqual(self.clim.thin(), ["kurz"])
        self.assertEqual(self.clim.thin(minimum=10), [])
        self.assertEqual(sorted(self.clim.thin(minimum=99)), ["kurz", "lang"])

    def test_unknown_lake_is_not_an_error(self):
        self.assertEqual(self.clim.years("gibtsnicht"), 0)
        self.assertEqual(self.clim.describe_coverage("gibtsnicht"), "")
