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

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_REFERENCE = (1991, 2020)
DEFAULT_WINDOW = 7
#: Mindestzahl an Werten je Kalendertag-Fenster, damit ein Normalwert gilt.
MIN_SAMPLES = 20


def add_daynumber(frame: pd.DataFrame) -> pd.DataFrame:
    """Ergänzt ``year`` und ``doy`` (1..365, schaltjahrbereinigt)."""
    dates = pd.DatetimeIndex(frame["date"])
    doy = np.asarray(dates.dayofyear)
    leap = np.asarray(dates.is_leap_year)
    return frame.assign(
        year=np.asarray(dates.year),
        doy=doy - (leap & (doy >= 60)).astype(int),
    )


@dataclass
class Climatology:
    """Langjähriges Tagesmittel je See."""

    table: pd.DataFrame  # lake_key, doy, mean, sd, p10, p90, min, max, n
    ref_start: int
    ref_end: int
    window: int

    @property
    def label(self) -> str:
        return f"{self.ref_start}–{self.ref_end}"

    def coverage(self) -> pd.DataFrame:
        """Je See: Anzahl belegter Kalendertage und Jahre im Bezugszeitraum."""
        return (
            self.table.groupby("lake_key")
            .agg(tage=("doy", "size"), werte_min=("n", "min"), werte_median=("n", "median"))
            .reset_index()
        )


def build(
    frame: pd.DataFrame,
    reference: tuple[int, int] = DEFAULT_REFERENCE,
    window: int = DEFAULT_WINDOW,
    min_samples: int = MIN_SAMPLES,
) -> Climatology:
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
        by_doy = {d: g.to_numpy() for d, g in group.groupby("doy")["temp_c"]}
        for doy in range(1, 366):
            offsets = ((np.arange(doy - window, doy + window + 1) - 1) % 365) + 1
            pool = np.concatenate([by_doy[o] for o in offsets if o in by_doy] or [np.array([])])
            if pool.size < min_samples:
                continue
            rows.append(
                {
                    "lake_key": lake_key,
                    "doy": doy,
                    "mean": pool.mean(),
                    "sd": pool.std(ddof=1) if pool.size > 1 else 0.0,
                    "p10": np.percentile(pool, 10),
                    "p90": np.percentile(pool, 90),
                    "min": pool.min(),
                    "max": pool.max(),
                    "n": pool.size,
                }
            )

    if not rows:
        raise SystemExit(
            f"Im Bezugszeitraum {ref_start}–{ref_end} gibt es an keinem Kalendertag "
            f"mindestens {min_samples} Werte. Bezugszeitraum verlängern oder "
            "--min-samples senken."
        )
    return Climatology(pd.DataFrame(rows), ref_start, ref_end, window)


def with_anomaly(frame: pd.DataFrame, clim: Climatology) -> pd.DataFrame:
    """Verknüpft Messwerte mit dem Normalwert und rechnet die Abweichung aus."""
    data = add_daynumber(frame)
    merged = data.merge(clim.table, on=["lake_key", "doy"], how="left")
    merged["anomaly"] = merged["temp_c"] - merged["mean"]
    with np.errstate(divide="ignore", invalid="ignore"):
        merged["z"] = merged["anomaly"] / merged["sd"].replace(0.0, np.nan)
    return merged


def season_summary(
    annotated: pd.DataFrame, year: int, months: tuple[int, int] = (5, 9)
) -> pd.DataFrame:
    """Mittlere Abweichung je See in der Badesaison eines Jahres."""
    month = pd.DatetimeIndex(annotated["date"]).month
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
    subset["month"] = pd.DatetimeIndex(subset["date"]).month
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
