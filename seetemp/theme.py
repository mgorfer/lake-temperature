"""Farb- und Typografie-Vorgaben für alle Grafiken.

Hell- und Dunkelvariante sind getrennt gewählt (nicht algorithmisch
invertiert). Die kategoriale Palette ist gegen Farbfehlsichtigkeit geprüft;
für Abweichungen kommt eine divergierende Blau/Rot-Skala mit neutraler
grauer Mitte zum Einsatz -- warm und kalt lesen sich als Gegensatz, die Mitte
als "nichts".
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib as mpl


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    panel: str
    text: str
    text_secondary: str
    text_muted: str
    grid: str
    series_1: str  # kategorial, Steckplatz 1
    series_2: str  # kategorial, Steckplatz 2
    warm: str  # divergierender Pol "wärmer als normal"
    cool: str  # divergierender Pol "kälter als normal"
    neutral: str  # divergierende Mitte
    ink: str  # Linie der aktuellen Reihe
    band: str  # Streubereich des Bezugszeitraums
    band_inner: float  # Deckkraft 10.-90. Perzentil
    band_outer: float  # Deckkraft Min/Max-Hülle
    fill_alpha: float  # Deckkraft der Abweichungsflächen


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    panel="#f4f3ef",
    text="#0b0b0b",
    text_secondary="#52514e",
    text_muted="#8a8983",
    grid="#e6e5e1",
    series_1="#2a78d6",
    series_2="#eb6834",
    warm="#d03b3b",
    cool="#2a78d6",
    neutral="#f0efec",
    ink="#17171a",
    band="#d9d8d3",
    band_inner=0.75,
    band_outer=0.45,
    fill_alpha=0.30,
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    panel="#242422",
    text="#ffffff",
    text_secondary="#c3c2b7",
    text_muted="#8f8e85",
    grid="#333330",
    series_1="#3987e5",
    series_2="#d95926",
    warm="#e66767",
    cool="#3987e5",
    neutral="#383835",
    ink="#f2f1ec",
    band="#55554f",
    band_inner=0.80,
    band_outer=0.42,
    fill_alpha=0.42,
)

THEMES = {"light": LIGHT, "dark": DARK}


def apply(theme: Theme) -> None:
    """Setzt die rcParams: dünne Marken, zurückhaltendes Raster, viel Luft."""
    mpl.rcParams.update(
        {
            "figure.facecolor": theme.surface,
            "figure.dpi": 200,
            "savefig.facecolor": theme.surface,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.28,
            "axes.facecolor": theme.surface,
            "axes.edgecolor": theme.grid,
            "axes.labelcolor": theme.text_secondary,
            "axes.titlecolor": theme.text,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": theme.grid,
            "grid.linewidth": 0.7,
            "grid.linestyle": "-",
            "xtick.color": theme.text_secondary,
            "ytick.color": theme.text_secondary,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 10,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2.0,
            "lines.solid_capstyle": "round",
        }
    )


def diverging_cmap(theme: Theme):
    """Blau -> neutrales Grau -> Rot, für Abweichungskarten."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        f"anomalie_{theme.name}",
        [theme.cool, "#8fb8e8" if theme.name == "light" else "#2d5a8c", theme.neutral,
         "#e8a09a" if theme.name == "light" else "#8c4444", theme.warm],
    )
