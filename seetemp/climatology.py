"""Berechnung des langjährigen Mittels und der Abweichungen davon.

Vorgehen, angelehnt an die übliche Praxis für Klimanormalwerte:

* Bezugszeitraum ist frei wählbar, Vorgabe ist die WMO-Normalperiode
  1991--2020.
* Der Normalwert wird je Kalendertag gebildet, dabei aber über ein
  gleitendes Fenster von +/- ``window`` Tagen aus allen Bezugsjahren
  aggregiert. Das glättet die Tag-zu-Tag-Zufälligkeit einer einzelnen
  Messreihe, ohne den Jahresgang zu verschleifen.
* Neben dem Mittel werden Streuung, 10./90. Perzentil und die Extremwerte
  des Bezugszeitraums geführt -- erst diese Bandbreite macht eine einzelne
  Abweichung interpretierbar.
* Der 29. Februar wird auf den 28. gelegt, damit alle Jahre dieselbe
  365-Tage-Achse teilen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_REFERENCE = (1991, 2020)
DEFAULT_WINDOW = 7
#: Mindestzahl an Werten je Kalendertag-Fenster, damit ein Normalwert gilt.
MIN_SAMPLES = 20
#: Bei Monatsmitteln ist ein Wert ein ganzer Monat -- entsprechend weniger.
MIN_SAMPLES_MONTHLY = 10
#: Ab wie vielen Jahren ein Normalwert als solide gilt. Die WMO-Normalperiode
#: umfasst dreissig; darunter wird die Angabe eigens ausgewiesen.
MIN_YEARS = 20


def add_daynumber(frame: pd.DataFrame) -> pd.DataFrame:
    """Ergänzt ``year``, ``month`` und ``doy`` (1..365, schaltjahrbereinigt)."""
    dates = pd.DatetimeIndex(frame["date"])
    doy = np.asarray(dates.dayofyear)
    leap = np.asarray(dates.is_leap_year)
    return frame.assign(
        year=np.asarray(dates.year),
        month=np.asarray(dates.month),
        doy=doy - (leap & (doy >= 60)).astype(int),
    )


@dataclass
class Climatology:
    """Langjähriger Normalwert je See -- je Kalendertag oder je Monat."""

    table: pd.DataFrame  # lake_key, <key>, mean, sd, p10, p90, min, max, n
    ref_start: int
    ref_end: int
    window: int
    resolution: str = "daily"
    #: Je See: auf wie vielen Jahren der Normalwert steht (jahre, von, bis,
    #: werte). Ein Mittel aus elf Jahren ist kein Mittel aus dreissig, und
    #: das gehört sichtbar gemacht statt in der Zahl zu verschwinden.
    coverage: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def key(self) -> str:
        """Spalte, über die Messwert und Normalwert zusammenfinden."""
        return "doy" if self.resolution == "daily" else "month"

    @property
    def label(self) -> str:
        return f"{self.ref_start}–{self.ref_end}"

    @property
    def method(self) -> str:
        if self.resolution == "daily":
            return f"gleitendes ±{self.window}-Tage-Fenster"
        return "Monatsmittel"

    def years(self, lake_key: str) -> int:
        """Anzahl Jahre, die zum Normalwert dieses Sees beitragen."""
        if self.coverage.empty:
            return 0
        row = self.coverage[self.coverage["lake_key"] == lake_key]
        return int(row["jahre"].iloc[0]) if len(row) else 0

    def describe_coverage(self, lake_key: str) -> str:
        """Kurzfassung für die Beschriftung, etwa "aus 11 Jahren (2009–2020)"."""
        if self.coverage.empty:
            return ""
        row = self.coverage[self.coverage["lake_key"] == lake_key]
        if not len(row):
            return ""
        r = row.iloc[0]
        return f"aus {int(r['jahre'])} Jahren ({int(r['von'])}–{int(r['bis'])})"

    def thin(self, minimum: int = MIN_YEARS) -> list[str]:
        """Seen, deren Normalwert auf weniger als ``minimum`` Jahren steht."""
        if self.coverage.empty:
            return []
        mager = self.coverage[self.coverage["jahre"] < minimum]
        return mager.sort_values("jahre")["lake_key"].tolist()


def _summarise(pool: np.ndarray, lake_key: str, key: str, value: int) -> dict:
    return {
        "lake_key": lake_key,
        key: value,
        "mean": pool.mean(),
        "sd": pool.std(ddof=1) if pool.size > 1 else 0.0,
        "p10": np.percentile(pool, 10),
        "p90": np.percentile(pool, 90),
        "min": pool.min(),
        "max": pool.max(),
        "n": pool.size,
    }


def build(
    frame: pd.DataFrame,
    reference: tuple[int, int] = DEFAULT_REFERENCE,
    window: int = DEFAULT_WINDOW,
    min_samples: int | None = None,
    resolution: str = "daily",
) -> Climatology:
    """Normalwerte für den Bezugszeitraum.

    ``resolution="daily"`` bildet je Kalendertag ein gleitendes Fenster über
    alle Bezugsjahre. ``resolution="monthly"`` ist der Weg für Quellen, die
    nur Monatsmittel liefern (etwa eHYD): dort ist der Monat selbst die
    Stützstelle, ein Fenster wäre sinnlos.
    """
    if resolution not in ("daily", "monthly"):
        raise ValueError(f"Unbekannte Auflösung: {resolution!r}")
    if min_samples is None:
        min_samples = MIN_SAMPLES if resolution == "daily" else MIN_SAMPLES_MONTHLY

    ref_start, ref_end = reference
    data = add_daynumber(frame)
    ref = data[(data["year"] >= ref_start) & (data["year"] <= ref_end)]
    if ref.empty:
        raise SystemExit(
            f"Keine Daten im Bezugszeitraum {ref_start}–{ref_end}. "
            "Bitte --ref anpassen oder eine längere Reihe verwenden."
        )

    rows = []
    for lake_key, group in ref.groupby("lake_key", sort=True):
        if resolution == "daily":
            by_doy = {d: g.to_numpy() for d, g in group.groupby("doy")["temp_c"]}
            for doy in range(1, 366):
                offsets = ((np.arange(doy - window, doy + window + 1) - 1) % 365) + 1
                pool = np.concatenate(
                    [by_doy[o] for o in offsets if o in by_doy] or [np.array([])]
                )
                if pool.size >= min_samples:
                    rows.append(_summarise(pool, lake_key, "doy", doy))
        else:
            for month, values in group.groupby("month")["temp_c"]:
                pool = values.to_numpy()
                if pool.size >= min_samples:
                    rows.append(_summarise(pool, lake_key, "month", int(month)))

    if not rows:
        stelle = "Kalendertag" if resolution == "daily" else "Monat"
        raise SystemExit(
            f"Im Bezugszeitraum {ref_start}–{ref_end} gibt es an keinem {stelle} "
            f"mindestens {min_samples} Werte. Bezugszeitraum verlängern oder "
            "--min-samples senken."
        )

    table = pd.DataFrame(rows)
    # Wie gut ist der Normalwert je See belegt? Nur Seen, für die er
    # überhaupt zustande kam.
    belegt = ref[ref["lake_key"].isin(table["lake_key"].unique())]
    coverage = (
        belegt.groupby("lake_key")
        .agg(jahre=("year", "nunique"), von=("year", "min"), bis=("year", "max"),
             werte=("temp_c", "size"))
        .reset_index()
    )
    return Climatology(table, ref_start, ref_end, window, resolution, coverage)


def with_anomaly(frame: pd.DataFrame, clim: Climatology) -> pd.DataFrame:
    """Verknüpft Messwerte mit dem Normalwert und rechnet die Abweichung aus."""
    data = add_daynumber(frame)
    merged = data.merge(clim.table, on=["lake_key", clim.key], how="left")
    merged["anomaly"] = merged["temp_c"] - merged["mean"]
    with np.errstate(divide="ignore", invalid="ignore"):
        merged["z"] = merged["anomaly"] / merged["sd"].replace(0.0, np.nan)
    return merged


def season_summary(
    annotated: pd.DataFrame, year: int, months: tuple[int, int] = (5, 9)
) -> pd.DataFrame:
    """Mittlere Abweichung je See in der Badesaison eines Jahres."""
    month = annotated["month"]
    mask = (
        (annotated["year"] == year)
        & (month >= months[0])
        & (month <= months[1])
        & annotated["anomaly"].notna()
    )
    subset = annotated[mask]
    if subset.empty:
        return pd.DataFrame(columns=["lake_key", "anomaly", "temp_c", "mean", "tage"])
    return (
        subset.groupby("lake_key")
        .agg(
            anomaly=("anomaly", "mean"),
            temp_c=("temp_c", "mean"),
            mean=("mean", "mean"),
            tage=("temp_c", "size"),
        )
        .reset_index()
        .sort_values("anomaly", ascending=False)
    )


def monthly_anomaly(annotated: pd.DataFrame, year: int) -> pd.DataFrame:
    """Matrix See x Monat der mittleren Abweichung eines Jahres."""
    subset = annotated[(annotated["year"] == year) & annotated["anomaly"].notna()].copy()
    if subset.empty:
        return pd.DataFrame()
    return subset.pivot_table(index="lake_key", columns="month", values="anomaly", aggfunc="mean")


def swim_days(
    annotated: pd.DataFrame,
    threshold: float = 22.0,
    through_doy: int | None = None,
    coverage: float = 0.85,
):
    """Tage je Jahr und See mit Wassertemperatur >= ``threshold``.

    Ist das Vergleichsjahr noch nicht zu Ende, muss auch der Bezugszeitraum
    am selben Kalendertag abgeschnitten werden -- sonst stünde eine halbe
    Saison gegen eine ganze. Dafür ``through_doy`` setzen.

    Jahre, in denen weniger als ``coverage`` des betrachteten Zeitraums
    gemessen wurde, fallen heraus: Datenlücken sollen nicht als kurze
    Badesaison erscheinen.
    """
    data = annotated
    limit = 365
    if through_doy is not None:
        data = data[data["doy"] <= through_doy]
        limit = through_doy
    grouped = data.groupby(["lake_key", "year"]).agg(
        tage=("temp_c", "size"),
        warm=("temp_c", lambda s: int((s >= threshold).sum())),
    )
    return grouped[grouped["tage"] >= coverage * limit].reset_index()
