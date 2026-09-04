"""Erzeugung der PNG-Grafiken."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from . import climatology as clim_mod
from . import theme as theme_mod
from .lakes import BY_KEY

MONTH_STARTS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_LABELS = ["Jän", "Feb", "Mär", "Apr", "Mai", "Jun",
                "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
MONTH_NAMES = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember"]
MINUS = "\u2212"


def num(value: float, digits: int = 1, signed: bool = False) -> str:
    """Zahl in österreichischer Schreibweise: Dezimalkomma, echtes Minus."""
    text = f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"
    if signed and abs(value) < 0.5 * 10**-digits:
        text = text.lstrip("+-")  # kein "-0,0"
        text = "±" + text
    return text.replace("-", MINUS).replace(".", ",")


def long_date(stamp) -> str:
    return f"{stamp.day}. {MONTH_NAMES[stamp.month - 1]} {stamp.year}"


def de_axis(ax, axis: str = "both", digits: int = 1) -> None:
    """Achsenbeschriftung mit Dezimalkomma."""
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _: num(v, digits))
    if axis in ("x", "both"):
        ax.xaxis.set_major_formatter(fmt)
    if axis in ("y", "both"):
        ax.yaxis.set_major_formatter(fmt)


# ---------------------------------------------------------------- Grundgerüst

def _titleblock(fig, th, title: str, subtitle: str, top: float = 0.972) -> None:
    """Titel und (mehrzeiliger) Untertitel linksbündig über der Zeichenfläche."""
    height = fig.get_size_inches()[1]
    fig.text(0.012, top, title, color=th.text, fontsize=15, fontweight="bold", va="top")
    fig.text(0.012, top - 0.34 / height, subtitle, color=th.text_secondary, fontsize=9.5,
             va="top", linespacing=1.5)


def _footer(fig, th, text: str) -> None:
    fig.text(0.012, 0.012, text, color=th.text_muted, fontsize=8, va="bottom")


def _watermark(fig, th, active: bool) -> None:
    if not active:
        return
    fig.text(
        0.5, 0.46, "DEMO-DATEN", color=th.text_muted, alpha=0.10, fontsize=52,
        fontweight="bold", ha="center", va="center", rotation=24, zorder=0,
    )


def _month_axis(ax, th) -> None:
    ax.set_xlim(1, 365)
    ax.set_xticks([s + 14 for s in MONTH_STARTS])
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_xticks(MONTH_STARTS, minor=True)
    ax.grid(False, which="major", axis="x")
    ax.grid(True, which="minor", axis="x", color=th.grid, linewidth=0.7)


def _axes(fig, left: float, right: float, header_in: float, footer_in: float):
    """Zeichenfläche mit Rändern in Zoll -- unabhängig von der Figurhöhe."""
    height = fig.get_size_inches()[1]
    bottom = footer_in / height
    top = 1.0 - header_in / height
    return fig.add_axes([left, bottom, right - left, top - bottom])


def _despine(ax, th) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(th.grid)


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


# ------------------------------------------------------- 1: Jahresgang je See

def lake_season(
    annotated: pd.DataFrame,
    clim: clim_mod.Climatology,
    lake_key: str,
    year: int,
    th: theme_mod.Theme,
    source: str,
    is_demo: bool,
    out: Path,
) -> Path | None:
    lake = BY_KEY[lake_key]
    norm = clim.table[clim.table["lake_key"] == lake_key].sort_values("doy")
    current = annotated[
        (annotated["lake_key"] == lake_key) & (annotated["year"] == year)
    ].sort_values("doy")
    if norm.empty or current.empty:
        return None

    fig = plt.figure(figsize=(9.6, 5.9))
    ax = fig.add_axes([0.068, 0.105, 0.90, 0.655])
    _despine(ax, th)

    d, m = norm["doy"].to_numpy(), norm["mean"].to_numpy()
    ax.fill_between(d, norm["min"], norm["max"], color=th.band, alpha=th.band_outer, linewidth=0,
                    zorder=1)
    ax.fill_between(d, norm["p10"], norm["p90"], color=th.band, alpha=th.band_inner, linewidth=0,
                    zorder=2)
    ax.plot(d, m, color=th.text_secondary, linewidth=1.6, linestyle=(0, (4.5, 2.4)), zorder=4)

    # Aktuelle Reihe auf das Normalwertraster legen, damit die Flächen passen.
    joined = current[["doy", "temp_c"]].merge(norm[["doy", "mean"]], on="doy", how="inner")
    cd = joined["doy"].to_numpy()
    ct = joined["temp_c"].to_numpy()
    cm = joined["mean"].to_numpy()
    ax.fill_between(cd, cm, ct, where=ct >= cm, color=th.warm, alpha=th.fill_alpha, linewidth=0,
                    interpolate=True, zorder=3)
    ax.fill_between(cd, cm, ct, where=ct < cm, color=th.cool, alpha=th.fill_alpha, linewidth=0,
                    interpolate=True, zorder=3)
    ax.plot(cd, ct, color=th.ink, linewidth=2.0, zorder=5)

    # Ausgewählte Direktbeschriftung: nur der letzte Wert der aktuellen Reihe.
    if len(cd):
        ax.scatter([cd[-1]], [ct[-1]], s=42, color=th.ink, zorder=6,
                   edgecolor=th.surface, linewidth=2)
        right_edge = cd[-1] > 322  # Beschriftung sonst am Rand abgeschnitten
        ax.annotate(
            f"{num(ct[-1])} °C",
            (cd[-1], ct[-1]), textcoords="offset points",
            xytext=(-9 if right_edge else 9, 0), ha="right" if right_edge else "left",
            color=th.text, fontsize=10, fontweight="bold", va="center",
        )

    ax.set_ylabel("Wassertemperatur (°C)")
    ax.set_ylim(bottom=0)
    de_axis(ax, "y", digits=0)
    _month_axis(ax, th)

    handles = [
        Line2D([], [], color=th.ink, linewidth=2, label=f"Jahresgang {year}"),
        Line2D([], [], color=th.text_secondary, linewidth=1.6, linestyle=(0, (4.5, 2.4)),
               label=f"Mittel {clim.label}"),
        Patch(facecolor=th.band, alpha=th.band_inner, label=f"10.–90. Perzentil {clim.label}"),
        Patch(facecolor=th.band, alpha=th.band_outer, label=f"Min/Max {clim.label}"),
        Patch(facecolor=th.warm, alpha=th.fill_alpha, label="wärmer als das Mittel"),
        Patch(facecolor=th.cool, alpha=th.fill_alpha, label="kälter als das Mittel"),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.012, 0.770), ncol=3,
               labelcolor=th.text_secondary, handlelength=2.4, columnspacing=1.6,
               borderpad=0.0, handletextpad=0.7, labelspacing=0.55)

    season = current[current["date"].dt.month.between(5, 9)]
    dev = season["anomaly"].mean() if not season.empty else float("nan")
    last = current.iloc[-1]
    subtitle = (
        f"{lake.altitude_m} m Seehöhe · {num(lake.area_km2, 2)} km² · "
        f"max. {lake.max_depth_m} m tief\n"
        f"Letzter Wert {long_date(last['date'])}: {num(last['temp_c'])} °C "
        f"({num(last['anomaly'], signed=True)} K gegenüber dem Tagesnormalwert)"
        + (f" · Saisonmittel Mai–September: {num(dev, signed=True)} K"
           if not math.isnan(dev) else "")
    )
    _titleblock(fig, th, f"{lake.name} — {year} im Vergleich zum Mittel {clim.label}", subtitle)
    _footer(fig, th, f"Quelle: {source} · Normalwert: gleitendes ±{clim.window}-Tage-Fenster "
                     f"über {clim.ref_start}–{clim.ref_end}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# ------------------------------------------- 2: Abweichungsübersicht alle Seen

def anomaly_overview(
    summary: pd.DataFrame, clim, year: int, th, source: str, is_demo: bool, out: Path
) -> Path | None:
    if summary.empty:
        return None
    data = summary.sort_values("anomaly")
    names = [BY_KEY[k].name for k in data["lake_key"]]
    values = data["anomaly"].to_numpy()
    colors = [th.warm if v >= 0 else th.cool for v in values]

    fig = plt.figure(figsize=(9.6, 0.40 * len(data) + 2.05))
    ax = _axes(fig, 0.20, 0.955, header_in=1.15, footer_in=0.90)
    _despine(ax, th)
    ax.barh(names, values, color=colors, height=0.46, zorder=3)
    ax.axvline(0, color=th.text_secondary, linewidth=1.0, zorder=4)
    ax.grid(False, axis="y")
    ax.set_xlabel(f"Abweichung vom Mittel {clim.label} (K)")
    de_axis(ax, "x")
    for name, value, temp in zip(names, values, data["temp_c"]):
        ax.annotate(
            f"{num(value, signed=True)} K   ({num(temp)} °C)",
            (value, name), xytext=(6 if value >= 0 else -6, 0), textcoords="offset points",
            va="center", ha="left" if value >= 0 else "right",
            color=th.text, fontsize=9,
        )
    lo, hi = min(0.0, values.min()), max(0.0, values.max())
    room = 0.44 * (hi - lo or 1.0)  # Platz für die Direktbeschriftung
    ax.set_xlim(lo - room, hi + room)
    ax.tick_params(axis="y", labelsize=10)
    for label in ax.get_yticklabels():
        label.set_color(th.text)

    _titleblock(fig, th, f"Badesaison {year} (Mai–September) im langjährigen Vergleich",
                f"Mittlere Abweichung der Tageswerte vom Normalwert {clim.label}; "
                f"in Klammern das Saisonmittel des Jahres {year}.")
    _footer(fig, th, f"Quelle: {source}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# --------------------------------------------------- 3: Monatsmatrix (Heatmap)

def monthly_heatmap(matrix: pd.DataFrame, clim, year: int, th, source, is_demo, out: Path):
    if matrix.empty:
        return None
    matrix = matrix.reindex(sorted(matrix.index, key=lambda k: BY_KEY[k].name))
    names = [BY_KEY[k].name for k in matrix.index]
    values = matrix.to_numpy(dtype=float)
    span = np.nanmax(np.abs(values)) or 1.0

    fig = plt.figure(figsize=(9.6, 0.38 * len(names) + 2.05))
    ax = _axes(fig, 0.175, 0.875, header_in=1.15, footer_in=0.62)
    cmap = theme_mod.diverging_cmap(th)
    image = ax.imshow(values, cmap=cmap, vmin=-span, vmax=span, aspect="auto")
    ax.set_xticks(range(values.shape[1]))
    ax.set_xticklabels([MONTH_LABELS[int(c) - 1] for c in matrix.columns])
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9.5)
    for label in ax.get_yticklabels() + ax.get_xticklabels():
        label.set_color(th.text)
    ax.grid(False)
    ax.set_xticks(np.arange(-0.5, values.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(names), 1), minor=True)
    ax.tick_params(which="minor", length=0)
    # 2px-Fuge in Flächenfarbe statt Rahmen um die Zellen.
    ax.grid(which="minor", color=th.surface, linewidth=2)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = values[i, j]
            if np.isnan(v):
                continue
            r, g, b, _ = cmap((v + span) / (2 * span))
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            ax.text(j, i, num(v, signed=True), ha="center", va="center", fontsize=8.5,
                    color="#111111" if luminance > 0.55 else "#ffffff")

    bar = fig.colorbar(image, ax=ax, fraction=0.030, pad=0.02)
    bar.set_label("Abweichung (K)", color=th.text_secondary, fontsize=9)
    bar.ax.tick_params(colors=th.text_secondary, labelsize=8)
    de_axis(bar.ax, "y", digits=0)
    bar.outline.set_visible(False)

    _titleblock(fig, th, f"Monatliche Abweichung vom Mittel {clim.label} — {year}",
                "Positiv (rot) = wärmer als im langjährigen Mittel, "
                "negativ (blau) = kälter. Werte in Kelvin.")
    _footer(fig, th, f"Quelle: {source}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# --------------------------------------------------------- 4: Badetage-Bilanz

def swim_days(days: pd.DataFrame, clim, year: int, threshold: float, th, source, is_demo,
              out: Path, through: pd.Timestamp | None = None):
    if days.empty:
        return None
    ref = days[days["year"].between(clim.ref_start, clim.ref_end)]
    now = days[days["year"] == year].set_index("lake_key")["warm"]
    if ref.empty or now.empty:
        return None
    normal = ref.groupby("lake_key")["warm"].mean()
    keys = [k for k in normal.index if k in now.index]
    keys.sort(key=lambda k: now[k] - normal[k])
    if not keys:
        return None

    names = [BY_KEY[k].name for k in keys]
    pos = np.arange(len(keys), dtype=float)
    height = 0.30

    fig = plt.figure(figsize=(9.6, 0.52 * len(keys) + 2.25))
    ax = _axes(fig, 0.20, 0.955, header_in=1.55, footer_in=0.88)
    _despine(ax, th)
    ax.barh(pos + height / 2 + 0.012, [now[k] for k in keys], height=height,
            color=th.series_1, label=f"{year}", zorder=3)
    ax.barh(pos - height / 2 - 0.012, [normal[k] for k in keys], height=height,
            color=th.series_2, label=f"Mittel {clim.label}", zorder=3)
    ax.set_yticks(pos)
    ax.set_yticklabels(names, fontsize=10)
    for label in ax.get_yticklabels():
        label.set_color(th.text)
    ax.grid(False, axis="y")
    ax.set_xlabel(f"Tage mit ≥ {threshold:g} °C")
    for i, k in enumerate(keys):
        ax.annotate(f"{now[k]:.0f}", (now[k], i + height / 2 + 0.012), xytext=(5, 0),
                    textcoords="offset points", va="center", color=th.text, fontsize=9)
        ax.annotate(f"{normal[k]:.0f}", (normal[k], i - height / 2 - 0.012), xytext=(5, 0),
                    textcoords="offset points", va="center", color=th.text_secondary,
                    fontsize=9)
    ax.set_xlim(0, max(now.max(), normal.max()) * 1.16)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower left",
               bbox_to_anchor=(0.012, 1 - 1.20 / fig.get_size_inches()[1]), ncol=2,
               labelcolor=th.text_secondary, handlelength=1.4, columnspacing=1.8,
               borderpad=0.0, handletextpad=0.6)

    period = (f"1. Jänner bis {long_date(through)}" if through is not None
              else f"im ganzen Jahr {year}")
    _titleblock(fig, th, f"Badetage {year} gegenüber dem Mittel {clim.label}",
                f"Tage mit einem Tagesmittel von mindestens {threshold:g} °C, {period}. "
                "Der Vergleichszeitraum\nist auf denselben Kalenderausschnitt beschnitten; "
                "sortiert nach der Differenz.")
    _footer(fig, th, f"Quelle: {source} · nur Jahre mit weitgehend lückenloser Messreihe")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# ---------------------------------------- 5: Jahresreihe der Saisonabweichung

def anomaly_trend(annotated: pd.DataFrame, clim, th, source, is_demo, out: Path,
                  months: tuple[int, int] = (5, 9)):
    month = pd.DatetimeIndex(annotated["date"]).month
    subset = annotated[month.isin(range(months[0], months[1] + 1))
                       & annotated["anomaly"].notna()]
    if subset.empty:
        return None
    series = (
        subset.groupby(["lake_key", "year"])
        .agg(anomaly=("anomaly", "mean"), tage=("anomaly", "size"))
        .reset_index()
    )
    series = series[series["tage"] >= 120]
    keys = sorted(series["lake_key"].unique(), key=lambda k: BY_KEY[k].name)
    if not keys:
        return None

    cols = 4
    rows = math.ceil(len(keys) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(9.6, 1.55 * rows + 1.6), sharex=True,
                             sharey=True)
    axes = np.atleast_1d(axes).ravel()
    span = float(np.nanmax(np.abs(series["anomaly"]))) * 1.06 or 1.0

    for ax, key in zip(axes, keys):
        part = series[series["lake_key"] == key].sort_values("year")
        colors = [th.warm if v >= 0 else th.cool for v in part["anomaly"]]
        ax.bar(part["year"], part["anomaly"], color=colors, width=0.78, zorder=3)
        ax.axhline(0, color=th.text_secondary, linewidth=0.9, zorder=4)
        ax.set_title(BY_KEY[key].name, fontsize=10, color=th.text, loc="left", pad=5)
        ax.set_ylim(-span, span)
        ax.grid(False, axis="x")
        _despine(ax, th)
        ax.tick_params(labelsize=8)
        de_axis(ax, "y", digits=0)
    for ax in axes[len(keys):]:
        ax.set_visible(False)
    for ax in axes[: len(keys)]:
        ax.tick_params(axis="x", rotation=0)

    fig.supylabel("Abweichung (K)", color=th.text_secondary, fontsize=9.5, x=0.008)
    figure_height = 1.55 * rows + 1.6
    fig.subplots_adjust(left=0.068, right=0.985, top=1 - 1.30 / figure_height,
                        bottom=0.62 / figure_height, hspace=0.50, wspace=0.20)
    _titleblock(fig, th, f"Saisonmittel Mai–September je Jahr, Abweichung vom Mittel {clim.label}",
                "Jeder Balken ist ein Sommer. Rot = wärmer als das langjährige Mittel, "
                "blau = kälter.")
    _footer(fig, th, f"Quelle: {source}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)
