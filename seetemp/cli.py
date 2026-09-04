"""Kommandozeile: Daten holen, Normalwerte rechnen, PNGs schreiben."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import charts, climatology, lakes as lakes_mod, theme as theme_mod
from .sources import csvfile, synthetic

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "stations.json"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="seetemp",
        description="Vergleicht die Wassertemperatur der Kärntner Seen mit dem "
                    "langjährigen Mittel und schreibt das Ergebnis als PNG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Beispiele:\n"
               "  python -m seetemp --source demo --year 2026\n"
               "  python -m seetemp --source ehyd --ref 1991-2020 --lakes woerthersee faaker_see\n"
               "  python -m seetemp --source ktn\n"
               "  python -m seetemp --source csv --csv meine_messungen.csv\n",
    )
    p.add_argument("--source", choices=["demo", "ehyd", "ktn", "csv"], default="demo",
                   help="Datenquelle (Vorgabe: demo -- synthetische Werte, netzunabhängig)")
    p.add_argument("--csv", type=Path, help="Pfad zur CSV-Datei bei --source csv")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                   help="Stationszuordnung für die Online-Quellen")
    p.add_argument("--lakes", nargs="*", metavar="KEY",
                   help="Auswahl von Seen (Vorgabe: alle). Schlüssel siehe --list-lakes")
    p.add_argument("--list-lakes", action="store_true", help="Verfügbare Seen ausgeben")
    p.add_argument("--probe", action="store_true",
                   help="Nur nachsehen, was eHYD je Messstelle tatsächlich anbietet "
                        "(Diagnose, erzeugt keine Grafiken)")
    p.add_argument("--year", type=int, default=date.today().year,
                   help="Vergleichsjahr (Vorgabe: laufendes Jahr)")
    p.add_argument("--ref", default="1991-2020", metavar="VON-BIS",
                   help="Bezugszeitraum für das langjährige Mittel (Vorgabe: 1991-2020)")
    p.add_argument("--window", type=int, default=climatology.DEFAULT_WINDOW,
                   help="Halbe Breite des gleitenden Fensters in Tagen (Vorgabe: 7)")
    p.add_argument("--min-samples", type=int, default=None,
                   help="Mindestzahl Werte je Stützstelle (Vorgabe: 20 bei Tages-, "
                        "10 bei Monatswerten)")
    p.add_argument("--resolution", choices=["auto", "daily", "monthly"], default="auto",
                   help="Zeitliche Auflösung der Auswertung (Vorgabe: aus der Quelle)")
    p.add_argument("--threshold", type=float, default=22.0,
                   help="Schwelle für die Badetage-Bilanz in °C (Vorgabe: 22)")
    p.add_argument("--theme", choices=["light", "dark", "both"], default="both",
                   help="Farbschema der Grafiken (Vorgabe: both)")
    p.add_argument("--out", type=Path, default=ROOT / "output", help="Ausgabeverzeichnis")
    p.add_argument("--demo-start", type=int, default=1991,
                   help="Erstes Jahr der Demoreihe (nur --source demo)")
    return p


def parse_reference(text: str) -> tuple[int, int]:
    try:
        start, end = (int(x) for x in text.replace("/", "-").split("-", 1))
    except ValueError:
        raise SystemExit(f"--ref erwartet die Form JJJJ-JJJJ, bekam {text!r}")
    if end <= start:
        raise SystemExit("--ref: das Endjahr muss nach dem Startjahr liegen.")
    return start, end


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_data(args, selected):
    if args.source == "demo":
        return synthetic.generate(
            selected, date(args.demo_start, 1, 1), date.today()
        )
    if args.source == "csv":
        if not args.csv:
            raise SystemExit("--source csv verlangt zusätzlich --csv PFAD")
        return csvfile.load(args.csv)

    config = load_config(args.config)
    if args.source == "ehyd":
        from .sources import ehyd

        stations = config.get("ehyd", {}).get("stations", {})
        template = config.get("ehyd", {}).get("url_template", ehyd.DEFAULT_URL_TEMPLATE)
        wanted = {lake.key: stations.get(lake.key, "") for lake in selected}
        return ehyd.fetch(wanted, template)

    from .sources import ktn

    return ktn.fetch(config.get("ktn", {}))


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_lakes:
        for lake in lakes_mod.LAKES:
            print(f"{lake.key:<20} {lake.name} ({lake.altitude_m} m, max. {lake.max_depth_m} m)")
        return 0

    selected = lakes_mod.resolve(args.lakes)

    if args.probe:
        from .sources import ehyd

        config = load_config(args.config).get("ehyd", {})
        stations = config.get("stations", {})
        wanted = {lake.key: stations.get(lake.key, "") for lake in selected}
        if not any(str(v).strip() for v in wanted.values()):
            raise SystemExit("Keine HZB-Nummern in config/stations.json eingetragen.")
        print(ehyd.probe(wanted))
        return 0

    reference = parse_reference(args.ref)

    dataset = load_data(args, selected)
    frame = dataset.frame[dataset.frame["lake_key"].isin({l.key for l in selected})]
    unknown = set(dataset.frame["lake_key"]) - set(lakes_mod.BY_KEY)
    if unknown:
        print(f"Hinweis: unbekannte Seeschlüssel übersprungen: {', '.join(sorted(unknown))}",
              file=sys.stderr)
    if frame.empty:
        raise SystemExit("Die Quelle lieferte für die gewählten Seen keine Werte.")

    span = pd.DatetimeIndex(frame["date"])
    resolution = dataset.resolution if args.resolution == "auto" else args.resolution
    aufloesung = "Tageswerte" if resolution == "daily" else "Monatsmittel"
    print(f"Quelle:          {dataset.source}"
          + ("   [SYNTHETISCHE DEMODATEN]" if dataset.is_demo else ""))
    print(f"Auflösung:       {aufloesung}")
    count = f"{len(frame):,}".replace(",", ".")
    print(f"Zeitraum:        {span.min():%d.%m.%Y} – {span.max():%d.%m.%Y}"
          f"  ({count} Werte, {frame['lake_key'].nunique()} Seen)")

    clim = climatology.build(frame, reference, args.window, args.min_samples, resolution)
    annotated = climatology.with_anomaly(frame, clim)
    print(f"Bezugszeitraum:  {clim.label} ({clim.method})")

    if not (annotated["year"] == args.year).any():
        available = sorted(annotated["year"].unique())
        raise SystemExit(f"Für {args.year} liegen keine Werte vor. Vorhanden: "
                         f"{available[0]}–{available[-1]}")

    summary = climatology.season_summary(annotated, args.year)
    matrix = climatology.monthly_anomaly(annotated, args.year)
    year_rows = annotated[annotated["year"] == args.year]
    last_day = year_rows["date"].max()
    partial = last_day < pd.Timestamp(year=args.year, month=12, day=31)
    skipped: list[str] = []
    if resolution == "daily":
        through_doy = int(year_rows.loc[year_rows["date"].idxmax(), "doy"]) if partial else None
        days = climatology.swim_days(annotated, args.threshold, through_doy)
    else:
        # Aus Monatsmitteln lassen sich keine einzelnen Badetage zählen.
        days = pd.DataFrame()
        skipped.append("Badetage-Bilanz (braucht Tageswerte, Quelle liefert Monatsmittel)")

    themes = ["light", "dark"] if args.theme == "both" else [args.theme]
    written: list[Path] = []
    for name in themes:
        th = theme_mod.THEMES[name]
        theme_mod.apply(th)
        target = args.out / name
        common = dict(th=th, source=dataset.source, is_demo=dataset.is_demo)

        written += [p for p in [
            charts.anomaly_overview(summary, clim, args.year,
                                    out=target / f"01_uebersicht_abweichung_{args.year}.png",
                                    **common),
            charts.monthly_heatmap(matrix, clim, args.year,
                                   out=target / f"02_monatsmatrix_{args.year}.png", **common),
            charts.swim_days(days, clim, args.year, args.threshold,
                             out=target / f"03_badetage_{args.year}.png",
                             through=last_day if partial else None, **common)
            if not days.empty else None,
            charts.anomaly_trend(annotated, clim,
                                 out=target / "04_saisonabweichung_zeitreihe.png", **common),
        ] if p]

        for lake in selected:
            path = charts.lake_season(
                annotated, clim, lake.key, args.year,
                out=target / "seen" / f"{lake.key}_{args.year}.png", **common,
            )
            if path:
                written.append(path)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": dataset.source,
        "is_demo": dataset.is_demo,
        "resolution": resolution,
        "year": args.year,
        "reference": clim.label,
        "method": clim.method,
        "threshold_c": args.threshold,
        "lakes": [{"key": l.key, "name": l.name} for l in selected],
        "data_from": f"{span.min():%Y-%m-%d}",
        "data_until": f"{span.max():%Y-%m-%d}",
        "values": int(len(frame)),
        "skipped": skipped,
        "notes": dataset.notes,
        "files": sorted(str(p.relative_to(args.out)) for p in written),
    }
    (args.out / "run.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\n{len(written)} PNG-Dateien geschrieben nach {args.out}/")
    for path in written[:6]:
        print(f"  {path.relative_to(args.out)}")
    if len(written) > 6:
        print(f"  … und {len(written) - 6} weitere")
    if dataset.is_demo:
        print("\nACHTUNG: Demomodus. Die Grafiken beruhen auf synthetischen Werten "
              "und sind nur zur Veranschaulichung.")
    for note in skipped:
        print(f"\nÜbersprungen: {note}")
    if dataset.notes:
        print("\nHinweise der Quelle:")
        for note in dataset.notes[:15]:
            print(f"  · {note}")
        if len(dataset.notes) > 15:
            print(f"  … und {len(dataset.notes) - 15} weitere")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
