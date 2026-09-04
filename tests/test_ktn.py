"""Prüfungen der Quelle "Hydrographischer Dienst Kärnten".

Der Dienst antwortet Rechenzentrums-Adressen nicht, sein Feldschema ist
nicht dokumentiert. Der Adapter muss deshalb die Felder selbst erkennen und
bei einem unbekannten Aufbau sagen, was er vorgefunden hat.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from seetemp.sources import ktn

FIXTURE = Path(__file__).parent / "fixtures" / "hdkaernten_see.json"
#: Zuordnung wie in config/stations.json -- über die HZB-Nummer.
CONFIG = {
    "hzb_to_lake_key": {"woerthersee": "212985", "turnersee": "217331"},
    "name_to_lake_key": {"Rauschele See": "rauschele_see"},
}


def real_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class RealServiceTest(unittest.TestCase):
    """Gegen einen Auszug der tatsächlichen Antwort des Dienstes."""

    def setUp(self):
        self.data = ktn.load(real_payload(), CONFIG)
        self.frame = self.data.frame.set_index("lake_key")

    def test_reads_the_geojson_schema(self):
        self.assertEqual(set(self.frame.index),
                         {"woerthersee", "turnersee", "rauschele_see"})
        self.assertIn("gewaesser", self.data.notes[0])
        self.assertIn("letzter_wert_wt", self.data.notes[0])

    def test_maps_by_hzb_number_and_falls_back_to_the_name(self):
        # Wörthersee und Turnersee tragen eine HZB-Nummer, Rauschele See nicht.
        self.assertAlmostEqual(self.frame.loc["woerthersee", "temp_latest"], 25.4)
        self.assertAlmostEqual(self.frame.loc["turnersee", "temp_latest"], 25.6)
        self.assertAlmostEqual(self.frame.loc["rauschele_see", "temp_latest"], 25.0)

    def test_iso_timestamp_is_not_read_day_first(self):
        """"2026-09-04T21:00:00+01:00" ist der 4. September, nicht der 9. April."""
        self.assertEqual(self.frame.loc["woerthersee", "date"], pd.Timestamp("2026-09-04"))
        self.assertEqual(self.frame.loc["woerthersee", "latest_at"],
                         pd.Timestamp("2026-09-04 22:15"))

    def test_daily_mean_comes_from_the_series_not_the_single_value(self):
        row = self.frame.loc["woerthersee"]
        self.assertGreater(row["readings"], 1)
        self.assertNotAlmostEqual(row["temp_c"], row["temp_latest"], places=3)

    def test_passes_on_the_services_own_warning_and_licence(self):
        joined = " | ".join(self.data.notes)
        self.assertIn("ungeprüfte Rohdaten", joined)
        self.assertIn("CC-BY-4.0", joined)


class DailyMeanTest(unittest.TestCase):
    def test_averages_only_the_last_window(self):
        series = [
            {"date": "2026-09-03T08:00:00+01:00", "value": 10.0},   # zu alt
            {"date": "2026-09-04T08:00:00+01:00", "value": 20.0},
            {"date": "2026-09-04T20:00:00+01:00", "value": 24.0},
        ]
        mean, count = ktn.daily_mean(series, hours=24)
        self.assertAlmostEqual(mean, 22.0)
        self.assertEqual(count, 2)

    def test_empty_or_broken_series(self):
        self.assertEqual(ktn.daily_mean([]), (None, 0))
        self.assertEqual(ktn.daily_mean([{"date": "unsinn", "value": "x"}]), (None, 0))


class LocalTimeTest(unittest.TestCase):
    def test_midnight_reading_keeps_its_local_date(self):
        """Eine Umrechnung nach UTC schöbe den Wert auf den Vortag."""
        self.assertEqual(ktn._stamp("2026-09-05T00:30:00+01:00"),
                         pd.Timestamp("2026-09-05 00:30"))

MAPPING = {
    "Wörther See": "woerthersee",
    "Ossiacher See": "ossiacher_see",
    "Turnersee": "turnersee",
}


def response(payload, status=200):
    fake = mock.Mock()
    fake.json.return_value = payload
    fake.status_code = status
    fake.raise_for_status.return_value = None
    fake.headers = {"content-type": "application/json"}
    return fake


class FieldDetectionTest(unittest.TestCase):
    def test_recognises_german_field_names(self):
        keys = ["Seename", "Wassertemperatur", "Messdatum", "Wasserstand"]
        self.assertEqual(ktn._pick(keys, ktn.NAME_HINTS), "Seename")
        self.assertEqual(ktn._pick(keys, ktn.TEMP_HINTS), "Wassertemperatur")
        self.assertEqual(ktn._pick(keys, ktn.DATE_HINTS), "Messdatum")

    def test_recognises_short_and_upper_case_names(self):
        keys = ["NAME", "WT", "DATUM"]
        self.assertEqual(ktn._pick(keys, ktn.NAME_HINTS), "NAME")
        self.assertEqual(ktn._pick(keys, ktn.TEMP_HINTS), "WT")

    def test_both_spellings_of_an_umlaut_fold_together(self):
        """Sonst greift die Zuordnung nicht, wenn der Dienst "Woerthersee" schreibt."""
        self.assertEqual(ktn._fold("Wörther See"), ktn._fold("Woerther See"))
        self.assertEqual(ktn._fold("Wörthersee"), "woerthersee")
        self.assertEqual(ktn._fold(" Millstätter  See "), "millstaettersee")
        self.assertEqual(ktn._fold("Weißensee"), ktn._fold("Weissensee"))

    def test_reads_numbers_with_comma_and_unit(self):
        self.assertAlmostEqual(ktn._number("21,4 °C"), 21.4)
        self.assertAlmostEqual(ktn._number(19.2), 19.2)
        self.assertAlmostEqual(ktn._number("-0,5"), -0.5)
        self.assertIsNone(ktn._number(None))
        self.assertIsNone(ktn._number("kein Wert"))


class RecordShapeTest(unittest.TestCase):
    def test_geojson(self):
        payload = {"type": "FeatureCollection",
                   "features": [{"properties": {"a": 1}}, {"properties": {"a": 2}}]}
        self.assertEqual(ktn.records(payload), [{"a": 1}, {"a": 2}])

    def test_arcgis(self):
        payload = {"features": [{"attributes": {"a": 1}}]}
        self.assertEqual(ktn.records(payload), [{"a": 1}])

    def test_plain_list_and_keyed_object(self):
        self.assertEqual(ktn.records([{"a": 1}]), [{"a": 1}])
        keyed = ktn.records({"2001": {"a": 1}, "2002": {"a": 2}})
        self.assertEqual([r["_schluessel"] for r in keyed], ["2001", "2002"])


class SchemaRobustnessTest(unittest.TestCase):
    """Erfundene Schemata -- der Adapter darf nicht auf eines festgelegt sein."""

    PAYLOAD = [
        # Absichtlich in der Umschrift -- der Dienst schreibt nicht garantiert Umlaute.
        {"Seename": "Woerther See", "Wassertemperatur": "24,3", "Messdatum": "04.09.2026"},
        {"Seename": "Ossiacher See", "Wassertemperatur": "23,1", "Messdatum": "04.09.2026"},
        {"Seename": "Turnersee", "Wassertemperatur": "25,0", "Messdatum": "04.09.2026"},
        {"Seename": "Unbekannter Teich", "Wassertemperatur": "19,0",
         "Messdatum": "04.09.2026"},
    ]

    def test_reads_values_and_maps_lakes(self):
        with mock.patch.object(ktn.requests, "get", return_value=response(self.PAYLOAD)):
            data = ktn.fetch({"name_to_lake_key": MAPPING})
        self.assertEqual(set(data.frame["lake_key"]), {"woerthersee", "ossiacher_see",
                                                       "turnersee"})
        row = data.frame.set_index("lake_key").loc["woerthersee"]
        self.assertAlmostEqual(row["temp_c"], 24.3)
        self.assertEqual(row["date"], pd.Timestamp("2026-09-04"))
        self.assertTrue(any("Unbekannter Teich" in n for n in data.notes))

    def test_keeps_only_the_latest_value_per_lake(self):
        payload = [
            {"Seename": "Wörther See", "Wassertemperatur": "20,0",
             "Messdatum": "01.09.2026"},
            {"Seename": "Wörther See", "Wassertemperatur": "24,3",
             "Messdatum": "04.09.2026"},
        ]
        with mock.patch.object(ktn.requests, "get", return_value=response(payload)):
            data = ktn.fetch({"name_to_lake_key": MAPPING})
        self.assertEqual(len(data.frame), 1)
        self.assertAlmostEqual(data.frame.iloc[0]["temp_c"], 24.3)

    def test_unknown_schema_reports_what_it_found(self):
        payload = [{"foo": "Wörther See", "bar": 24.3}]
        with mock.patch.object(ktn.requests, "get", return_value=response(payload)):
            with self.assertRaises(SystemExit) as caught:
                ktn.fetch({"name_to_lake_key": MAPPING})
        message = str(caught.exception)
        self.assertIn("foo", message)      # nennt die vorhandenen Felder
        self.assertIn("bar", message)
        self.assertIn("Beispielsatz", message)

    def test_configured_field_names_win(self):
        payload = [{"x_name": "Wörther See", "x_temp": "24,3", "x_zeit": "04.09.2026"}]
        with mock.patch.object(ktn.requests, "get", return_value=response(payload)):
            data = ktn.fetch({
                "name_to_lake_key": MAPPING,
                "fields": {"name": "x_name", "temperature": "x_temp", "date": "x_zeit"},
            })
        self.assertAlmostEqual(data.frame.iloc[0]["temp_c"], 24.3)

    def test_unreachable_service_names_both_protocols(self):
        import requests as rq

        with mock.patch.object(ktn.requests, "get",
                               side_effect=rq.ConnectionError("boom")):
            with self.assertRaises(SystemExit) as caught:
                ktn.fetch({"name_to_lake_key": MAPPING})
        message = str(caught.exception)
        self.assertIn("https://info.ktn.gv.at", message)
        self.assertIn("http://info.ktn.gv.at", message)  # Rückfall wurde versucht
        self.assertIn("curl", message)                   # nennt einen Prüfbefehl

    def test_no_mappable_lake_lists_the_names_in_the_service(self):
        payload = [{"Seename": "Irgendein See", "Wassertemperatur": "20,0"}]
        with mock.patch.object(ktn.requests, "get", return_value=response(payload)):
            with self.assertRaises(SystemExit) as caught:
                ktn.fetch({"name_to_lake_key": MAPPING})
        self.assertIn("Irgendein See", str(caught.exception))


class AttachNormalsTest(unittest.TestCase):
    def test_lakes_without_a_long_series_keep_their_temperature(self):
        from seetemp import climatology
        from seetemp.cli import attach_normals

        dates = pd.date_range("1991-01-01", "2020-12-31", freq="D")
        reference = pd.DataFrame({"lake_key": "woerthersee", "date": dates, "temp_c": 12.0})
        clim = climatology.build(reference)

        live = pd.DataFrame({
            "lake_key": ["woerthersee", "turnersee"],
            "date": [pd.Timestamp("2026-07-01")] * 2,
            "temp_c": [14.5, 25.0],
        })
        current = attach_normals(live, clim).set_index("lake_key")
        self.assertAlmostEqual(current.loc["woerthersee", "anomaly"], 2.5)
        self.assertAlmostEqual(current.loc["turnersee", "temp_c"], 25.0)
        self.assertTrue(pd.isna(current.loc["turnersee", "anomaly"]))


class SnapshotTest(unittest.TestCase):
    """Abgelegte Abrufe überbrücken, dass der Dienst Rechenzentren schweigt."""

    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp())

    def write(self, name: str, stamp: str) -> Path:
        payload = real_payload()
        for feature in payload["features"]:
            q = feature["properties"]
            q["letzter_wert_wt_date"] = stamp
            q["werte"]["wassertemperatur"] = [{"date": stamp, "value": 21.0}]
        path = self.tmp / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_newest_snapshot_wins(self):
        self.write("hdkaernten_see-20260901T1200.json", "2026-09-01T12:00:00+01:00")
        neu = self.write("hdkaernten_see-20260904T2215.json", "2026-09-04T22:15:00+01:00")
        self.assertEqual(ktn.newest_snapshot(self.tmp), neu)

    def test_no_directory_no_snapshot(self):
        self.assertIsNone(ktn.newest_snapshot(self.tmp / "gibtsnicht"))

    def test_age_is_named_in_the_source(self):
        """Ein alter Wert als "aktuell" wäre eine Lüge."""
        now = ktn.local_now()
        frisch = self.write("hdkaernten_see-a.json",
                            f"{now - pd.Timedelta(minutes=20):%Y-%m-%dT%H:%M:00}+01:00")
        self.assertIn("frisch", ktn.load_snapshot(frisch, CONFIG).source)

        alt = self.write("hdkaernten_see-b.json",
                         f"{now - pd.Timedelta(days=6):%Y-%m-%dT%H:%M:00}+01:00")
        self.assertIn("6 Tage alt", ktn.load_snapshot(alt, CONFIG).source)

    def test_local_now_is_austrian_wall_clock(self):
        """Sonst ist ein eben abgerufener Wert im Rechenzentrum "in der Zukunft"."""
        versatz = ktn.local_now() - pd.Timestamp.now()
        self.assertGreaterEqual(versatz.total_seconds(), -60)
