"""Prüfungen für die Zahlen hinter der interaktiven Übersichtsseite."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from seetemp import webdaten


def punkte(key: str, werte: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame({"lake_key": key,
                         "when": [pd.Timestamp(w) for w, _ in werte],
                         "temp_c": [v for _, v in werte]})


class TrendTest(unittest.TestCase):
    """Verglichen werden zwei Tagesmittel, nicht der jüngste Wert mit vorhin."""

    def reihe(self, gestern: list[float], heute: list[float]) -> pd.DataFrame:
        werte = [(f"2026-09-17 {6 + 3 * i:02d}:00", v) for i, v in enumerate(gestern)]
        werte += [(f"2026-09-18 {6 + 3 * i:02d}:00", v) for i, v in enumerate(heute)]
        return punkte("woerthersee", werte)

    def test_mean_of_today_against_mean_of_yesterday(self):
        reihe = self.reihe([21.0, 22.0, 23.0, 22.0], [21.5, 22.5, 23.5, 22.5])
        self.assertAlmostEqual(webdaten.trend(reihe), 0.5)

    def test_the_daily_cycle_is_not_a_trend(self):
        # Beide Tage laufen gleich: morgens kühl, nachmittags warm. Kein Trend.
        reihe = self.reihe([20.0, 22.0, 24.0, 22.0], [20.0, 22.0, 24.0, 22.0])
        self.assertEqual(webdaten.trend(reihe), 0.0)

    def test_too_few_readings_no_trend(self):
        reihe = self.reihe([21.0, 22.0], [22.0, 23.0, 23.0, 23.0])
        self.assertIsNone(webdaten.trend(reihe))
        reihe = self.reihe([21.0, 22.0, 22.0, 22.0], [23.0])
        self.assertIsNone(webdaten.trend(reihe))

    def test_empty_series(self):
        self.assertIsNone(webdaten.trend(pd.DataFrame()))
        self.assertIsNone(webdaten.trend(None))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.current = pd.DataFrame([{
            "lake_key": "woerthersee", "date": pd.Timestamp("2026-09-18"),
            "temp_c": 23.24, "temp_latest": 23.1,
            "latest_at": pd.Timestamp("2026-09-18 15:00"),
            "mean": 22.8, "anomaly": 0.44,
        }, {
            # Ohne lange Reihe: Temperatur ja, Normalwert nein.
            "lake_key": "turnersee", "date": pd.Timestamp("2026-09-18"),
            "temp_c": 21.8, "temp_latest": 21.7,
            "latest_at": pd.Timestamp("2026-09-18 14:30"),
            "mean": float("nan"), "anomaly": float("nan"),
        }])
        self.recent = pd.concat([
            punkte("woerthersee", [("2026-09-16 16:00", 22.0), ("2026-09-16 22:00", 22.0),
                                   ("2026-09-17 04:00", 22.0), ("2026-09-17 10:00", 22.0),
                                   ("2026-09-17 16:00", 22.6), ("2026-09-17 22:00", 22.6),
                                   ("2026-09-18 04:00", 22.6), ("2026-09-18 10:00", 22.6),
                                   ("2026-09-18 15:00", 23.1)]),
            punkte("turnersee", [("2026-09-18 14:30", 21.7)]),
        ], ignore_index=True)
        self.daily = pd.DataFrame({
            "lake_key": ["woerthersee", "woerthersee"],
            "date": [pd.Timestamp("2026-09-17"), pd.Timestamp("2026-09-18")],
            "temp_c": [22.9, 23.24], "messungen": [48, 40],
        })

    def build(self, **extra):
        return webdaten.build(self.current, self.recent, self.daily,
                              source="Test", caveat="ungeprüft", **extra)

    def test_every_lake_gets_its_numbers(self):
        daten = self.build()
        woerther = next(s for s in daten["seen"] if s["key"] == "woerthersee")
        self.assertEqual(woerther["name"], "Wörthersee")
        self.assertEqual(woerther["jetzt"], 23.1)
        self.assertEqual(woerther["jetzt_um"], "2026-09-18T15:00")
        self.assertEqual(woerther["mittel_24h"], 23.2)
        self.assertEqual(woerther["normal"], 22.8)
        self.assertEqual(woerther["abweichung"], 0.4)
        self.assertEqual(woerther["trend_24h"], 0.7)   # (22,6·4+23,1)/5 − 22,0
        self.assertEqual(woerther["tage"], [["2026-09-17", 22.9, 48],
                                            ["2026-09-18", 23.24, 40]])

    def test_lake_without_a_normal_keeps_its_temperature(self):
        turner = next(s for s in self.build()["seen"] if s["key"] == "turnersee")
        self.assertEqual(turner["jetzt"], 21.7)
        self.assertIsNone(turner["normal"])
        self.assertIsNone(turner["abweichung"])
        self.assertIsNone(turner["trend_24h"])   # nur ein Wert, kein Gestern
        self.assertEqual(turner["tage"], [])

    def test_points_are_minutes_from_the_first_reading(self):
        daten = self.build()
        self.assertEqual(daten["t0"], "2026-09-16T16:00")
        woerther = next(s for s in daten["seen"] if s["key"] == "woerthersee")
        self.assertEqual(woerther["punkte"][:2], [[0, 22.0], [360, 22.0]])
        self.assertEqual(woerther["punkte"][-1], [2820, 23.1])
        turner = next(s for s in daten["seen"] if s["key"] == "turnersee")
        self.assertEqual(turner["punkte"], [[2790, 21.7]])

    def test_warmest_lake_comes_first(self):
        self.assertEqual([s["key"] for s in self.build()["seen"]],
                         ["woerthersee", "turnersee"])

    def test_stand_carries_the_carinthian_offset(self):
        """Der Browser rechnet das Alter gegen seine eigene Uhr -- dafür
        muss der Stempel sagen, in welcher Zone er steht (Sommerzeit: +02:00)."""
        daten = self.build()
        self.assertEqual(daten["stand_lokal"], "2026-09-18T15:00")
        self.assertTrue(daten["stand"].startswith("2026-09-18T15:00"))
        self.assertTrue(daten["stand"].endswith("+02:00"), daten["stand"])

    def test_source_caveat_and_threshold_travel_along(self):
        daten = self.build(threshold=20, hours=48, is_demo=True, reference="1991–2020")
        self.assertEqual(daten["quelle"], "Test")
        self.assertEqual(daten["hinweis"], "ungeprüft")
        self.assertEqual(daten["schwelle_c"], 20.0)
        self.assertEqual(daten["fenster_h"], 48)
        self.assertTrue(daten["normal_demo"])
        self.assertEqual(daten["bezug"], "1991–2020")

    def test_empty_inputs_give_an_empty_but_valid_file(self):
        daten = webdaten.build(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), source="x")
        self.assertEqual(daten["seen"], [])
        self.assertIsNone(daten["stand"])
        self.assertIsNone(daten["t0"])

    def test_points_only_lake_uses_its_newest_reading(self):
        recent = punkte("faaker_see", [("2026-09-18 10:00", 20.0),
                                       ("2026-09-18 11:00", 20.4)])
        daten = webdaten.build(pd.DataFrame(), recent, pd.DataFrame(), source="x")
        faak = daten["seen"][0]
        self.assertEqual(faak["jetzt"], 20.4)
        self.assertEqual(faak["jetzt_um"], "2026-09-18T11:00")
        self.assertIsNone(faak["normal"])

    def test_write_is_compact_json(self):
        tmp = Path(tempfile.mkdtemp())
        pfad = webdaten.write(self.build(), tmp / "aktuell.json")
        text = pfad.read_text(encoding="utf-8")
        self.assertNotIn("\n  ", text)              # nicht eingerückt
        self.assertIn("Wörthersee", text)           # kein \\u00f6
        self.assertEqual(json.loads(text)["seen"][0]["key"], "woerthersee")
