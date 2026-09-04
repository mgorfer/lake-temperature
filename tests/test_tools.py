"""Prüfungen für die Werkzeuge rund um die Veröffentlichung."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build_gallery  # noqa: E402
import summary  # noqa: E402

RUN = {
    "generated_at": "2026-09-04T20:00:00+00:00",
    "source": "eHYD — Hydrographischer Dienst Österreich",
    "is_demo": False,
    "resolution": "monthly",
    "year": 2026,
    "reference": "1991–2020",
    "method": "Monatsmittel",
    "lakes": [{"key": "woerthersee", "name": "Wörthersee"}],
    "data_from": "1976-01-01",
    "data_until": "2026-08-01",
    "values": 6084,
    "skipped": ["Badetage-Bilanz (braucht Tageswerte)"],
    "notes": ["woerthersee: HZB 212985"],
    "files": [],
}


class Counter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: dict[str, int] = {}
        self.sources: list[str] = []
        self.images: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        attrs = dict(attrs)
        if tag == "source":
            self.sources.append(attrs.get("srcset", ""))
        if tag == "img":
            self.images.append(attrs.get("src", ""))


class GalleryTest(unittest.TestCase):
    def build(self, run=None, files=("light", "dark")):
        run = run or RUN
        tmp = Path(tempfile.mkdtemp())
        for theme in files:
            (tmp / theme / "seen").mkdir(parents=True)
            for name in ("01_uebersicht_abweichung_2026.png", "02_monatsmatrix_2026.png",
                         "04_saisonabweichung_zeitreihe.png"):
                (tmp / theme / name).write_bytes(b"\x89PNG")
            (tmp / theme / "seen" / "woerthersee_2026.png").write_bytes(b"\x89PNG")
        (tmp / "run.json").write_text(json.dumps(run), encoding="utf-8")
        return tmp, build_gallery.render(tmp, run)

    def parse(self, markup):
        counter = Counter()
        counter.feed(markup)
        return counter

    def test_both_themes_produce_a_picture_element(self):
        _, markup = self.build()
        counter = self.parse(markup)
        # drei Übersichten plus ein See
        self.assertEqual(counter.tags["picture"], 4)
        self.assertTrue(all(s.startswith("dark/") for s in counter.sources))
        self.assertTrue(all(i.startswith("light/") for i in counter.images))

    def test_single_theme_falls_back_to_a_plain_image(self):
        _, markup = self.build(files=("light",))
        counter = self.parse(markup)
        self.assertNotIn("picture", counter.tags)
        self.assertEqual(len(counter.images), 4)

    def test_missing_chart_is_left_out_rather_than_linked_dead(self):
        # Die Badetage-Grafik gibt es bei Monatsmitteln nicht.
        _, markup = self.build()
        self.assertNotIn("03_badetage", markup)

    def test_demo_run_is_flagged_prominently(self):
        _, plain = self.build()
        self.assertNotIn("Demodaten", plain)
        _, demo = self.build({**RUN, "is_demo": True})
        self.assertIn("Demodaten", demo)

    def test_lake_names_are_escaped(self):
        run = {**RUN, "lakes": [{"key": "woerthersee", "name": "See <b>x</b>"}]}
        _, markup = self.build(run)
        self.assertNotIn("<b>x</b>", markup)
        self.assertIn("&lt;b&gt;", markup)

    def test_output_parses_as_html(self):
        _, markup = self.build()
        self.parse(markup)  # wirft bei kaputtem Markup
        self.assertTrue(markup.startswith("<!doctype html>"))
        self.assertIn('lang="de"', markup)
        self.assertIn("prefers-color-scheme", markup)


class SummaryTest(unittest.TestCase):
    def test_names_source_resolution_and_skips(self):
        text = summary.render(RUN)
        self.assertIn("eHYD", text)
        self.assertIn("Monatsmittel", text)
        self.assertIn("Übersprungen: Badetage-Bilanz", text)
        self.assertIn("6.084", text)  # Tausenderpunkt
        self.assertNotIn("Demodaten", text)

    def test_demo_run_carries_a_warning(self):
        self.assertIn("Demodaten", summary.render({**RUN, "is_demo": True}))


class YearSelectionTest(unittest.TestCase):
    """Amtliche Reihen erscheinen mit Verzug -- das laufende Kalenderjahr
    als Vorgabe ginge bei ihnen regelmässig ins Leere."""

    def setUp(self):
        import pandas as pd

        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "reihe.csv"
        dates = pd.date_range("1991-01-01", "2023-12-01", freq="MS")
        month = pd.DatetimeIndex(dates).month
        pd.DataFrame({
            "lake_key": "woerthersee",
            "date": dates,
            "temp_c": 12.0 + 8.0 * (month - 6.5).map(lambda m: 1 - abs(m) / 6),
        }).to_csv(self.csv, index=False)

    def run_cli(self, *extra):
        from seetemp import cli

        out = self.tmp / f"out{len(extra)}"
        return cli.run(["--source", "csv", "--csv", str(self.csv), "--resolution",
                        "monthly", "--theme", "light", "--out", str(out), *extra]), out

    def test_defaults_to_the_latest_year_with_data(self):
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        run = json.loads((out / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["year"], 2023)  # nicht das laufende Kalenderjahr

    def test_explicit_year_without_data_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli("--year", "2026")
        self.assertIn("2026", str(caught.exception))
        self.assertIn("1991", str(caught.exception))
