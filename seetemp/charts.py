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


def _month_axis(ax, th, resolution: str = "daily") -> None:
    """Jahresachse -- entweder 365 Tage oder 12 Monatsstützstellen."""
    if resolution == "daily":
        ax.set_xlim(1, 365)
        ax.set_xticks([s + 14 for s in MONTH_STARTS])
        ax.set_xticklabels(MONTH_LABELS)
        ax.set_xticks(MONTH_STARTS, minor=True)
    else:
        ax.set_xlim(0.6, 12.4)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(MONTH_LABELS)
        ax.set_xticks(np.arange(0.5, 13, 1), minor=True)
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
    key = clim.key
    norm = clim.table[clim.table["lake_key"] == lake_key].sort_values(key)
    current = annotated[
        (annotated["lake_key"] == lake_key) & (annotated["year"] == year)
    ].sort_values(key)
    if norm.empty or current.empty:
        return None

    fig = plt.figure(figsize=(9.6, 5.9))
    ax = fig.add_axes([0.068, 0.105, 0.90, 0.655])
    _despine(ax, th)

    d, m = norm[key].to_numpy(), norm["mean"].to_numpy()
    ax.fill_between(d, norm["min"], norm["max"], color=th.band, alpha=th.band_outer, linewidth=0,
                    zorder=1)
    ax.fill_between(d, norm["p10"], norm["p90"], color=th.band, alpha=th.band_inner, linewidth=0,
                    zorder=2)
    ax.plot(d, m, color=th.text_secondary, linewidth=1.6, linestyle=(0, (4.5, 2.4)), zorder=4)

    # Aktuelle Reihe auf das Normalwertraster legen, damit die Flächen passen.
    joined = current[[key, "temp_c"]].merge(norm[[key, "mean"]], on=key, how="inner")
    cd = joined[key].to_numpy()
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
        # Beschriftung sonst am rechten Rand abgeschnitten
        right_edge = cd[-1] > (322 if key == "doy" else 10.6)
        ax.annotate(
            f"{num(ct[-1])} °C",
            (cd[-1], ct[-1]), textcoords="offset points",
            xytext=(-9 if right_edge else 9, 0), ha="right" if right_edge else "left",
            color=th.text, fontsize=10, fontweight="bold", va="center",
        )

    ax.set_ylabel("Wassertemperatur (°C)")
    ax.set_ylim(bottom=0)
    de_axis(ax, "y", digits=0)
    _month_axis(ax, th, clim.resolution)

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

    season = current[current["month"].between(5, 9)]
    dev = season["anomaly"].mean() if not season.empty else float("nan")
    last = current.iloc[-1]
    if clim.resolution == "daily":
        stand, normal = f"Letzter Wert {long_date(last['date'])}", "Tagesnormalwert"
    else:
        stand = f"Letzter Monat {MONTH_NAMES[last['month'] - 1]} {last['date'].year}"
        normal = "Monatsnormalwert"
    belegung = clim.describe_coverage(lake_key)
    subtitle = (
        f"{lake.altitude_m} m Seehöhe · {num(lake.area_km2, 2)} km² · "
        f"max. {lake.max_depth_m} m tief"
        + (f" · Normalwert {belegung}" if belegung else "") + "\n"
        f"{stand}: {num(last['temp_c'])} °C "
        f"({num(last['anomaly'], signed=True)} K gegenüber dem {normal})"
        + (f" · Saisonmittel Mai–September: {num(dev, signed=True)} K"
           if not math.isnan(dev) else "")
    )
    _titleblock(fig, th, f"{lake.name} — {year} im Vergleich zum Mittel {clim.label}", subtitle)
    _footer(fig, th, f"Quelle: {source} · Normalwert: {clim.method} "
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
    # Ein Normalwert aus elf Jahren ist keiner aus dreissig. Die betroffenen
    # Seen bekommen einen Stern und unten eine Zeile, die ihn auflöst.
    duenn = set(clim.thin())
    names = [BY_KEY[k].name + (" *" if k in duenn else "") for k in data["lake_key"]]
    values = data["anomaly"].to_numpy()
    colors = [th.warm if v >= 0 else th.cool for v in values]

    fig = plt.figure(figsize=(9.6, 0.40 * len(data) + 2.05 + (0.3 if duenn else 0)))
    ax = _axes(fig, 0.20, 0.955, header_in=1.15 + (0.30 if duenn else 0), footer_in=0.90)
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

    hinweis = ""
    if duenn:
        aufzaehlung = ", ".join(
            f"{BY_KEY[k].name} {clim.describe_coverage(k)}" for k in clim.thin()
        )
        hinweis = f"\n* Normalwert auf schmalerer Grundlage: {aufzaehlung}."
    _titleblock(fig, th, f"Badesaison {year} (Mai–September) im langjährigen Vergleich",
                f"Mittlere Abweichung der Tageswerte vom Normalwert {clim.label}; "
                f"in Klammern das Saisonmittel des Jahres {year}." + hinweis)
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
    subset = annotated[annotated["month"].between(months[0], months[1])
                       & annotated["anomaly"].notna()]
    if subset.empty:
        return None
    series = (
        subset.groupby(["lake_key", "year"])
        .agg(anomaly=("anomaly", "mean"), tage=("anomaly", "size"))
        .reset_index()
    )
    # Eine Saison gilt als belegt, wenn genug Stützstellen darin liegen.
    minimum = 120 if clim.resolution == "daily" else 4
    series = series[series["tage"] >= minimum]
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

    # sharex blendet die Jahreszahlen überall ausser in der letzten Zeile aus.
    # Die letzte Zeile ist aber selten voll -- also beschriften wir in jeder
    # Spalte das unterste sichtbare Feld.
    for spalte in range(cols):
        sichtbar = [i for i in range(spalte, len(keys), cols)]
        if sichtbar:
            axes[sichtbar[-1]].tick_params(labelbottom=True)
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


# ------------------------------------------------ 6: Aktuelle Werte (heute)

def current_status(current: pd.DataFrame, clim, th, source, is_demo, out: Path,
                   measured_source: str = "", caveat: str = ""):
    """Aktuelle Werte je See gegen ihren Normalwert -- alles auf einer Achse.

    Der massive Balken ist das Tagesmittel der letzten 24 Stunden: nur das
    lässt sich mit einem Normalwert vergleichen, der selbst ein Mittel ist.
    Liegt es über dem Normalwert, ist der Überschuss warm eingefärbt; liegt
    es darunter, zeigt eine blasse Fläche, was fehlt. Die Marke sitzt auf dem
    Normalwert, der Punkt auf dem jüngsten Einzelwert -- er beantwortet, wie
    warm es gerade ist. Drei Grössen, eine Achse, alle in Grad Celsius.
    """
    if current.empty:
        return None
    data = current.sort_values("temp_c", ascending=True).reset_index(drop=True)
    names = [BY_KEY[k].name for k in data["lake_key"]]
    pos = np.arange(len(data), dtype=float)
    height = 0.42

    fig = plt.figure(figsize=(9.6, 0.46 * len(data) + 2.9))
    ax = _axes(fig, 0.20, 0.955, header_in=2.00, footer_in=0.88)
    _despine(ax, th)
    for i, row in data.iterrows():
        temp, mean = float(row["temp_c"]), row["mean"]
        if pd.isna(mean):
            ax.barh(i, temp, height=height, color=th.series_1, zorder=3)
            continue
        mean = float(mean)
        if temp >= mean:
            ax.barh(i, mean, height=height, color=th.series_1, zorder=3)
            ax.barh(i, temp - mean, left=mean, height=height, color=th.warm, zorder=3)
        else:
            ax.barh(i, temp, height=height, color=th.series_1, zorder=3)
            # Blass: das ist kein Messwert, sondern was zum Normalwert fehlt.
            ax.barh(i, mean - temp, left=temp, height=height, color=th.cool,
                    alpha=0.28, zorder=2)
        ax.vlines(mean, i - height / 2, i + height / 2, color=th.ink, linewidth=2,
                  zorder=5)

    # Jüngster Einzelwert, wo die Reihe einen hergibt.
    if "temp_latest" in data:
        latest = data["temp_latest"]
        shown = latest.notna() & (latest - data["temp_c"]).abs().gt(0.05)
        if shown.any():
            ax.scatter(latest[shown], np.asarray(pos)[shown.to_numpy()], s=40,
                       color=th.surface, edgecolor=th.ink, linewidth=1.8, zorder=6)

    ax.set_yticks(pos)
    ax.set_yticklabels(names, fontsize=10)
    for label in ax.get_yticklabels():
        label.set_color(th.text)
    ax.grid(False, axis="y")
    ax.set_xlabel("Wassertemperatur (°C)")
    de_axis(ax, "x", digits=0)

    span = float(max(data["temp_c"].max(), data["mean"].max(skipna=True) or 0))
    ax.set_xlim(0, span * 1.30)
    for i, row in data.iterrows():
        # Auch der Punkt für den jüngsten Wert darf die Beschriftung nicht berühren.
        end = max(float(row["temp_c"]),
                  float(row["mean"]) if pd.notna(row["mean"]) else 0.0,
                  float(row["temp_latest"]) if pd.notna(row.get("temp_latest")) else 0.0)
        if pd.isna(row["mean"]):
            text = f"{num(row['temp_c'])} °C   (kein Normalwert)"
        else:
            text = f"{num(row['temp_c'])} °C   {num(row['anomaly'], signed=True)} K"
        ax.annotate(text, (end, i), xytext=(13, 0), textcoords="offset points",
                    va="center", color=th.text, fontsize=9.5)

    handles = [
        Patch(facecolor=th.series_1, label="Mittel der letzten 24 h"),
        Line2D([], [], color=th.ink, linewidth=2, label=f"Normalwert {clim.label}"),
        Patch(facecolor=th.warm, label="darüber"),
        Patch(facecolor=th.cool, alpha=0.28, label="fehlt zum Normalwert"),
        Line2D([], [], marker="o", linestyle="none", markersize=7,
               markerfacecolor=th.surface, markeredgecolor=th.ink, markeredgewidth=1.8,
               label="jüngster Einzelwert"),
    ]
    fig.legend(handles=handles, loc="lower left",
               bbox_to_anchor=(0.012, 1 - 1.52 / fig.get_size_inches()[1]), ncol=3,
               labelcolor=th.text_secondary, handlelength=1.5, columnspacing=1.6,
               borderpad=0.0, handletextpad=0.6)

    if "latest_at" in data and data["latest_at"].notna().any():
        newest = pd.Timestamp(data["latest_at"].max())
        stand = f"{long_date(newest)}, {newest:%H:%M}"
    else:
        stand = long_date(pd.Timestamp(data["date"].max()))
    einheit = "Tagesnormalwert" if clim.resolution == "daily" else "Monatsnormalwert"
    _titleblock(
        fig, th, f"Aktuelle Wassertemperatur — Stand {stand}",
        f"Mittel der letzten 24 Stunden gegenüber dem {einheit} aus {clim.label}; "
        f"sortiert nach Temperatur.\nMesswerte: {measured_source or source}",
    )
    _footer(fig, th, ((caveat + " · ") if caveat else "") + f"Normalwert: {source}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# -------------------------------------- 5: Ein Monat über die ganze Reihe

def month_series(annotated: pd.DataFrame, month: int, min_values: int = 1) -> pd.DataFrame:
    """Das Mittel eines Kalendermonats je See und Jahr.

    ``min_values`` verwirft dünn belegte Monate: aus vier Tageswerten ein
    Monatsmittel zu bilden hiesse, einen Kälteeinbruch zum Monat zu erklären.
    Aus Monatsmitteln ist ein Wert je Jahr dagegen alles, was es gibt.
    """
    subset = annotated[(annotated["month"] == month) & annotated["temp_c"].notna()]
    if subset.empty:
        return pd.DataFrame(columns=["lake_key", "year", "temp_c", "werte"])
    reihe = (
        subset.groupby(["lake_key", "year"], as_index=False)
        .agg(temp_c=("temp_c", "mean"), werte=("temp_c", "size"))
    )
    return reihe[reihe["werte"] >= min_values]


def month_start_year(annotated: pd.DataFrame, month: int, lake_key: str,
                     min_values: int = 1) -> int | None:
    """Erstes Jahr, in dem ein bestimmter See diesen Monat belegt hat."""
    reihe = month_series(annotated, month, min_values)
    teil = reihe[reihe["lake_key"] == lake_key]
    return int(teil["year"].min()) if not teil.empty else None


def month_history(annotated: pd.DataFrame, clim, month: int, th, source, is_demo,
                  out: Path, min_values: int = 1, start_year: int | None = None,
                  start_label: str = ""):
    """Ein Kalendermonat über alle Jahre der Aufzeichnung, je See ein Feld.

    Die Linie ist das Monatsmittel des jeweiligen Jahres, die gestrichelte
    Waagrechte der Normalwert desselben Monats. Die Fläche dazwischen ist
    warm oder kühl eingefärbt -- dieselbe Bildsprache wie beim Jahresgang,
    damit man nicht umlernen muss.

    Der Titel jedes Feldes nennt die lineare Steigung über die vorhandenen
    Jahre. Das ist eine Ausgleichsgerade, keine Aussage über Signifikanz.

    ``start_year`` setzt den Beginn der gemeinsamen Jahresachse -- gedacht
    für den See mit der längsten Reihe, damit alle Felder denselben
    Ausschnitt zeigen. Frühere Werte anderer Seen fallen dann heraus; wie
    viele, sagt der Untertitel, damit nichts stillschweigend verschwindet.
    """
    reihe = month_series(annotated, month, min_values)
    if reihe.empty:
        return None
    frueher = 0
    if start_year is not None:
        frueher = int((reihe["year"] < start_year).sum())
        reihe = reihe[reihe["year"] >= start_year]
        if reihe.empty:
            return None
    keys = sorted(reihe["lake_key"].unique(), key=lambda k: BY_KEY[k].name)
    if not keys:
        return None

    # Normalwert desselben Monats je See.
    normal = {}
    if clim.resolution == "monthly":
        rows = clim.table[clim.table["month"] == month]
        normal = dict(zip(rows["lake_key"], rows["mean"]))
    else:
        starts = dict(zip(range(1, 13), MONTH_STARTS))
        tage = range(starts[month], (starts.get(month + 1) or 366))
        rows = clim.table[clim.table["doy"].isin(tage)]
        normal = rows.groupby("lake_key")["mean"].mean().to_dict()

    cols = 3
    rows_n = math.ceil(len(keys) / cols)
    height = 2.05 * rows_n + 2.3
    fig, axes = plt.subplots(rows_n, cols, figsize=(9.6, height), sharex=True)
    axes = np.atleast_1d(axes).ravel()

    for ax, key in zip(axes, keys):
        teil = reihe[reihe["lake_key"] == key].sort_values("year")
        jahre = teil["year"].to_numpy(dtype=float)
        werte = teil["temp_c"].to_numpy()
        mittel = normal.get(key)

        if mittel is not None and len(jahre):
            ax.axhline(mittel, color=th.text_secondary, linewidth=1.4,
                       linestyle=(0, (4.5, 2.4)), zorder=3)
            ax.fill_between(jahre, mittel, werte, where=werte >= mittel,
                            color=th.warm, alpha=th.fill_alpha, linewidth=0,
                            interpolate=True, zorder=2)
            ax.fill_between(jahre, mittel, werte, where=werte < mittel,
                            color=th.cool, alpha=th.fill_alpha, linewidth=0,
                            interpolate=True, zorder=2)
        ax.plot(jahre, werte, color=th.ink, linewidth=1.4, zorder=4)
        if len(jahre) <= 45:
            ax.scatter(jahre, werte, s=9, color=th.ink, zorder=5)

        titel = BY_KEY[key].name
        if len(jahre) >= 10:
            steigung = np.polyfit(jahre, werte, 1)[0] * 10
            ax.plot(jahre, np.poly1d(np.polyfit(jahre, werte, 1))(jahre),
                    color=th.series_2, linewidth=1.6, zorder=6)
            titel += f"   {num(steigung, signed=True)} K/Jahrzehnt"
        ax.set_title(titel, fontsize=9.5, color=th.text, loc="left", pad=5)
        ax.grid(False, axis="x")
        _despine(ax, th)
        ax.tick_params(labelsize=8)
        de_axis(ax, "y", digits=0)
        ax.margins(x=0.02)

    if start_year is not None:
        # sharex: ein Feld setzt die Achse für alle.
        axes[0].set_xlim(start_year - 0.8, int(reihe["year"].max()) + 0.8)

    for ax in axes[len(keys):]:
        ax.set_visible(False)

    # sharex blendet die Jahreszahlen ausserhalb der letzten Zeile aus; die ist
    # aber selten voll. Also beschriften wir in jeder Spalte das unterste Feld.
    for spalte in range(cols):
        sichtbar = list(range(spalte, len(keys), cols))
        if sichtbar:
            axes[sichtbar[-1]].tick_params(labelbottom=True)

    fig.supylabel("Wassertemperatur (°C)", color=th.text_secondary, fontsize=9.5, x=0.008)
    fig.subplots_adjust(left=0.075, right=0.985, top=1 - 1.72 / height,
                        bottom=0.60 / height, hspace=0.62, wspace=0.22)

    von, bis = int(reihe["year"].min()), int(reihe["year"].max())
    handles = [
        Line2D([], [], color=th.ink, linewidth=1.4, label=f"{MONTH_NAMES[month - 1]}-Mittel"),
        Line2D([], [], color=th.text_secondary, linewidth=1.4, linestyle=(0, (4.5, 2.4)),
               label=f"Normalwert {clim.label}"),
        Line2D([], [], color=th.series_2, linewidth=1.6, label="Ausgleichsgerade"),
    ]
    fig.legend(handles=handles, loc="lower left",
               bbox_to_anchor=(0.012, 1 - 1.45 / height), ncol=3,
               labelcolor=th.text_secondary, handlelength=2.2, columnspacing=1.8,
               borderpad=0.0, handletextpad=0.6)
    achse = f"Die Achse beginnt mit {von}"
    if start_year is not None and start_label:
        achse = f"Die Achse beginnt mit dem ersten {MONTH_NAMES[month - 1]} " \
                f"am {start_label} ({start_year})"
        if frueher:
            achse += f"; {frueher} früher gemessene Monatsmittel anderer Seen " \
                     "bleiben aussen vor"
    _titleblock(
        fig, th, f"Jeder {MONTH_NAMES[month - 1]} der Aufzeichnung — {von} bis {bis}",
        f"Monatsmittel je Jahr gegen den Normalwert {clim.label}. Die Reihen "
        f"beginnen unterschiedlich früh. {achse}.\nDie Gerade ist ein linearer "
        "Ausgleich über die jeweils vorhandenen Jahre, keine Signifikanzaussage.",
    )
    _footer(fig, th, f"Quelle: {source}")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# ------------------------------ 6: Das laufende Jahr in Tageswerten

def current_year_daily(daily: pd.DataFrame, clim, lake_key: str, year: int, th,
                       source, is_demo, out: Path, measured_source: str = "",
                       caveat: str = ""):
    """Tageswerte des laufenden Jahres gegen den langjährigen Normalwert.

    Die amtliche lange Reihe endet mit dem letzten Jahrbuch; was heuer
    geschieht, steht nur in den tagesaktuellen Messwerten. Beides gehört in
    ein Bild: der Normalwert als Treppe über das Jahr -- er ist ein
    Monatsmittel und wird deshalb auch als solches gezeichnet, nicht zu
    einer Kurve verschliffen, die er nicht ist -- und darüber die
    gemessenen Tagesmittel.
    """
    teil = daily[(daily["lake_key"] == lake_key)
                 & (pd.DatetimeIndex(daily["date"]).year == year)].sort_values("date")
    if teil.empty:
        return None
    norm = clim.table[clim.table["lake_key"] == lake_key]
    if norm.empty:
        return None

    lake = BY_KEY[lake_key]
    fig = plt.figure(figsize=(9.6, 5.6))
    ax = _axes(fig, 0.068, 0.968, header_in=1.62, footer_in=0.62)
    _despine(ax, th)

    # Normalwert als Treppe: je Monat ein waagrechtes Stück.
    kanten, mittel, unten, oben = [], [], [], []
    je_monat: dict[int, float] = {}
    for m in range(1, 13):
        if clim.resolution == "monthly":
            zeile = norm[norm["month"] == m]
        else:
            tage = range(MONTH_STARTS[m - 1], (MONTH_STARTS[m] if m < 12 else 366))
            zeile = norm[norm["doy"].isin(tage)]
        if zeile.empty:
            continue
        kanten.append(MONTH_STARTS[m - 1])
        mittel.append(zeile["mean"].mean())
        je_monat[m] = zeile["mean"].mean()
        unten.append(zeile["p10"].mean())
        oben.append(zeile["p90"].mean())
    if not kanten:
        return None
    kanten.append(366)
    schritt = lambda werte: np.array(werte + [werte[-1]])

    ax.fill_between(kanten, schritt(unten), schritt(oben), step="post",
                    color=th.band, alpha=th.band_inner, linewidth=0, zorder=1)
    ax.step(kanten, schritt(mittel), where="post", color=th.text_secondary,
            linewidth=1.6, linestyle=(0, (4.5, 2.4)), zorder=3)

    doy = np.asarray(pd.DatetimeIndex(teil["date"]).dayofyear, dtype=float)
    werte = teil["temp_c"].to_numpy()

    # Der Normalwert am jeweiligen Messtag -- der Wert der Treppe, auf der
    # der Tag liegt. Die Fläche dazwischen trägt dieselbe Farbe wie in den
    # übrigen Grafiken: warm über, kühl unter dem Normalwert.
    monate = np.asarray(pd.DatetimeIndex(teil["date"]).month)
    normal_am_tag = np.array([je_monat.get(int(m), np.nan) for m in monate])
    gueltig = ~np.isnan(normal_am_tag)
    if gueltig.any():
        ax.fill_between(doy, normal_am_tag, werte, where=gueltig & (werte >= normal_am_tag),
                        color=th.warm, alpha=th.fill_alpha, linewidth=0,
                        interpolate=True, zorder=4)
        ax.fill_between(doy, normal_am_tag, werte, where=gueltig & (werte < normal_am_tag),
                        color=th.cool, alpha=th.fill_alpha, linewidth=0,
                        interpolate=True, zorder=4)

    ax.plot(doy, werte, color=th.ink, linewidth=2.0, zorder=5)
    ax.scatter(doy, werte, s=26, color=th.ink, zorder=6, edgecolor=th.surface,
               linewidth=1.4)
    if len(doy):
        rechts = doy[-1] > 322
        text = f"{num(werte[-1])} °C"
        if gueltig[-1]:
            text += f"  ({num(werte[-1] - normal_am_tag[-1], signed=True)} K)"
        ax.annotate(text, (doy[-1], werte[-1]),
                    textcoords="offset points", xytext=(-11 if rechts else 11, 0),
                    ha="right" if rechts else "left", va="center",
                    color=th.text, fontsize=10, fontweight="bold")

    ax.set_ylabel("Wassertemperatur (°C)")
    ax.set_ylim(bottom=0)
    de_axis(ax, "y", digits=0)
    _month_axis(ax, th, "daily")

    handles = [
        Line2D([], [], color=th.ink, linewidth=2, label=f"Tagesmittel {year}"),
        Line2D([], [], color=th.text_secondary, linewidth=1.6, linestyle=(0, (4.5, 2.4)),
               label=f"Monatsnormalwert {clim.label}"),
        Patch(facecolor=th.band, alpha=th.band_inner,
              label=f"10.–90. Perzentil {clim.label}"),
    ]
    fig.legend(handles=handles, loc="lower left",
               bbox_to_anchor=(0.012, 1 - 1.18 / fig.get_size_inches()[1]), ncol=3,
               labelcolor=th.text_secondary, handlelength=2.2, columnspacing=1.8,
               borderpad=0.0, handletextpad=0.6)

    tage_n = len(teil)
    messungen = int(teil["messungen"].sum())
    von, bis = teil["date"].min(), teil["date"].max()
    zeitraum = (f"{von:%d.%m.}–{bis:%d.%m.}" if von != bis else f"{von:%d.%m.}")
    _titleblock(
        fig, th, f"{lake.name} — {year} in Tageswerten",
        f"{tage_n} Tag{'e' if tage_n != 1 else ''} ({zeitraum}) aus {messungen} "
        f"Einzelmessungen, gegen den Monatsnormalwert {clim.label}.\n"
        f"Messwerte: {measured_source or source}",
    )
    _footer(fig, th, ((caveat + " · ") if caveat else "")
            + f"Normalwert: {source} · Die Reihe wächst mit jedem abgelegten Abruf.")
    _watermark(fig, th, is_demo)
    return _save(fig, out)


# ---------------------------- 7: Alle Seen, die letzten 72 Stunden

#: Wochentage für die Zeitachse -- kurz, damit drei Tage nebeneinander passen.
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _spread(werte: np.ndarray, abstand: float, unten: float, oben: float) -> np.ndarray:
    """Beschriftungen auseinanderschieben, ohne ihre Reihenfolge zu ändern.

    Zwei Seen können auf ein Zehntelgrad gleich warm sein; ihre Namen lägen
    dann übereinander. Geschoben wird nur so weit wie nötig und nur in der
    Reihenfolge der Werte -- sonst zeigte der Fühler des einen Namens auf die
    Linie des anderen.
    """
    ziel = np.array(werte, dtype=float)
    reihe = np.argsort(ziel)
    gelegt = ziel[reihe]
    for i in range(1, len(gelegt)):                      # von unten nach oben
        gelegt[i] = max(gelegt[i], gelegt[i - 1] + abstand)
    ueberstand = gelegt[-1] - oben
    if ueberstand > 0:                                   # oben angestossen
        gelegt -= ueberstand
        for i in range(len(gelegt) - 2, -1, -1):
            gelegt[i] = min(gelegt[i], gelegt[i + 1] - abstand)
    gelegt = np.maximum(gelegt, unten)
    ergebnis = np.empty_like(gelegt)
    ergebnis[reihe] = gelegt
    return ergebnis


def recent_overview(points: pd.DataFrame, th, source, is_demo, out: Path,
                    hours: int = 72, measured_source: str = "", caveat: str = ""):
    """Alle Seen nebeneinander, die letzten Stunden in Einzelmessungen.

    Das ist das Bild für die Frage, die man im Sommer tatsächlich stellt:
    wo ist es gerade warm? Drei Tage sind alles, was der Dienst hergibt --
    dafür im Viertelstundentakt, also mit dem Tagesgang darin: nachts kühlt
    die Oberfläche ab, nachmittags steht die Spitze.

    Fünfzehn Seen vertragen keine fünfzehn Farben. Die Farbe folgt deshalb
    der Temperatur (dieselbe Skala für alle), und wer welcher See ist, steht
    als Name am rechten Rand neben seiner eigenen Linie.

    Kein Demo-Wasserzeichen: hier steht kein Normalwert im Bild, jede Zahl
    ist gemessen. Läuft die übrige Auswertung auf Demodaten, sagt das die
    Fusszeile -- aber diese Messwerte sind davon nicht betroffen.
    """
    if points is None or points.empty:
        return None
    data = points[points["lake_key"].isin(BY_KEY)].sort_values("when")
    if data.empty:
        return None
    keys = list(data["lake_key"].unique())

    ende = pd.Timestamp(data["when"].max())
    beginn = pd.Timestamp(data["when"].min())
    spanne = (ende - beginn).total_seconds() / 3600

    fig = plt.figure(figsize=(9.6, 6.4))
    ax = _axes(fig, 0.062, 0.775, header_in=1.66, footer_in=0.70)
    _despine(ax, th)

    # Nacht als blasses Feld: der Tagesgang der Seen liest sich damit von
    # selbst, ohne dass jede Delle erklärt werden müsste.
    nacht = None
    tag = beginn.normalize() - pd.Timedelta(days=1)
    while tag <= ende:
        von = max(tag + pd.Timedelta(hours=20), beginn)
        bis = min(tag + pd.Timedelta(days=1, hours=6), ende)
        if von < bis:
            nacht = ax.axvspan(von, bis, color=th.panel, zorder=0, linewidth=0)
        tag += pd.Timedelta(days=1)

    letzte = {k: float(data[data["lake_key"] == k]["temp_c"].iloc[-1]) for k in keys}
    ordnung = sorted(keys, key=lambda k: letzte[k])
    farbe = dict(zip(ordnung, theme_mod.sequential_colors(th, len(ordnung))))

    for key in keys:
        teil = data[data["lake_key"] == key]
        ax.plot(teil["when"], teil["temp_c"], color=farbe[key], linewidth=1.8,
                solid_joinstyle="round", zorder=3)
        ax.scatter([teil["when"].iloc[-1]], [teil["temp_c"].iloc[-1]], s=30,
                   color=farbe[key], edgecolor=th.surface, linewidth=1.4, zorder=5)

    hoch, tief = data["temp_c"].max(), data["temp_c"].min()
    luft = max(0.6, (hoch - tief) * 0.06)
    ax.set_ylim(tief - luft, hoch + luft)
    ax.set_xlim(beginn, ende + pd.Timedelta(minutes=30))
    ax.set_ylabel("Wassertemperatur (°C)")
    de_axis(ax, "y", digits=0)

    # Zeitachse: Marken alle sechs Stunden, beschriftet Mitternacht und Mittag.
    marken, beschriftung = [], []
    marke = beginn.ceil("6h")
    while marke <= ende:
        marken.append(marke)
        if marke.hour == 0:
            beschriftung.append(f"{WEEKDAYS[marke.weekday()]}\n{marke:%d.%m.}")
        elif marke.hour == 12:
            beschriftung.append("12 Uhr")
        else:
            beschriftung.append("")
        marke += pd.Timedelta(hours=6)
    ax.set_xticks(marken)
    ax.set_xticklabels(beschriftung, fontsize=8.5)
    ax.grid(True, axis="x", color=th.grid, linewidth=0.7)

    # Namen am rechten Rand, auseinandergeschoben, mit Fühler zur Linie.
    unten, oben = ax.get_ylim()
    abstand = (oben - unten) / 26
    ziel = _spread(np.array([letzte[k] for k in keys]), abstand, unten, oben)
    rechts = ax.get_xlim()[1]
    schritt = (rechts - ax.get_xlim()[0])
    for key, y in zip(keys, ziel):
        wert = letzte[key]
        ax.annotate(
            "", xy=(rechts + schritt * 0.012, y), xytext=(ende, wert),
            xycoords=("data", "data"), textcoords=("data", "data"),
            arrowprops=dict(arrowstyle="-", color=farbe[key], linewidth=0.8,
                            shrinkA=2, shrinkB=0),
            annotation_clip=False, zorder=4,
        )
        ax.annotate(
            f"{BY_KEY[key].name}   {num(wert)} °C", (rechts + schritt * 0.018, y),
            xycoords=("data", "data"), va="center", ha="left", fontsize=8.8,
            color=th.text, annotation_clip=False, zorder=6,
        )

    handles = [
        Line2D([], [], color=th.ramp[1], linewidth=1.8, label="Messreihe je See"),
        Line2D([], [], marker="o", linestyle="none", markersize=6,
               markerfacecolor=th.ramp[1], markeredgecolor=th.surface,
               markeredgewidth=1.4, label="jüngster Wert"),
    ]
    if nacht is not None:
        handles.append(Patch(facecolor=th.panel, label="Nacht (20–6 Uhr)"))
    fig.legend(handles=handles, loc="lower left",
               bbox_to_anchor=(0.012, 1 - 1.22 / fig.get_size_inches()[1]), ncol=3,
               labelcolor=th.text_secondary, handlelength=1.8, columnspacing=1.8,
               borderpad=0.0, handletextpad=0.6)

    stunden = int(round(spanne))
    _titleblock(
        fig, th, f"Alle Seen — die letzten {stunden} Stunden",
        f"Einzelmessungen von {long_date(beginn)}, {beginn:%H:%M} bis "
        f"{long_date(ende)}, {ende:%H:%M} — {len(data)} Werte aus {len(keys)} Seen.\n"
        f"Die Farbe folgt allein der Temperatur; die Namen stehen am rechten Rand. "
        f"Messwerte: {measured_source or source}",
    )
    _footer(fig, th, ((caveat + " · ") if caveat else "")
            + f"Mehr als {hours} Stunden gibt der Dienst nicht her — ein Archiv "
              "führt er nicht."
            + (" · Gemessene Werte; die Normalwerte der übrigen Grafiken sind "
               "Demodaten." if is_demo else ""))
    return _save(fig, out)
