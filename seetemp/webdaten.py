"""Die Zahlen hinter den Bildern: ``aktuell.json`` für die Übersichtsseite.

Die PNGs sind fertig gezeichnet. Wer am Handy einen See antippt und den
Wert unter dem Finger sehen will, braucht die Zahlen selbst -- in einer
Form, die ein Browser ohne Bibliothek zeichnen kann. Diese Datei trägt sie
zusammen: je See der Stand gegen den Normalwert, die Einzelmessungen der
letzten Stunden und die Tagesreihe über den ganzen Bestand.

Zeitstempel bleiben Kärntner Wanduhrzeit ohne Zone, wie überall in
``sources/ktn.py``. Nur ``stand`` trägt einen Versatz: damit rechnet der
Browser das Alter des Abrufs gegen seine eigene Uhr, egal wo er steht.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .lakes import BY_KEY
from .sources.ktn import ZEITZONE

#: Der Trend vergleicht das Mittel der letzten 24 Stunden mit dem der 24
#: Stunden davor -- nicht den jüngsten Wert mit dem von vorhin: der Tagesgang
#: der Oberfläche (nachts kühl, nachmittags warm) wäre sonst der "Trend".
#: Zwei Tagesmittel heben ihn heraus, und Lücken in der Reihe (ein
#: ausgelassener Abruf) verschieben sie kaum.
TREND_H = 24
#: So viele Einzelwerte braucht jedes der beiden Fenster mindestens. Aus
#: zwei Messungen ist kein Mittel, das einen Trend trägt.
TREND_MIN_WERTE = 4


def _rund(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    # "+ 0.0" macht aus -0.0 (gerundet aus -0.04) eine Null ohne Vorzeichen.
    return round(float(value), 1) + 0.0


def _minute(stamp: pd.Timestamp) -> str:
    return f"{stamp:%Y-%m-%dT%H:%M}"


def stand_iso(newest: pd.Timestamp) -> str:
    """Der jüngste Zeitpunkt mit Versatz, damit der Browser sein Alter kennt."""
    try:
        from zoneinfo import ZoneInfo

        return newest.to_pydatetime().replace(tzinfo=ZoneInfo(ZEITZONE)).isoformat(
            timespec="minutes")
    except Exception:          # ohne Zeitzonendaten bleibt die Wanduhrzeit
        return _minute(newest)


def trend(points: pd.DataFrame, hours: int = TREND_H,
          min_values: int = TREND_MIN_WERTE) -> float | None:
    """Mittel der letzten ``hours`` Stunden minus Mittel der ``hours`` davor.

    Fehlen in einem der beiden Fenster die Messungen, gibt es keinen Trend
    -- lieber keine Zahl als eine aus zwei Werten.
    """
    if points is None or points.empty:
        return None
    juengst = points["when"].max()
    grenze = juengst - pd.Timedelta(hours=hours)
    heute = points[points["when"] > grenze]["temp_c"]
    gestern = points[(points["when"] <= grenze)
                     & (points["when"] > grenze - pd.Timedelta(hours=hours))]["temp_c"]
    if len(heute) < min_values or len(gestern) < min_values:
        return None
    return _rund(float(heute.mean()) - float(gestern.mean()))


def build(current: pd.DataFrame, recent: pd.DataFrame, daily: pd.DataFrame, *,
          source: str, caveat: str = "", threshold: float = 22.0,
          hours: int = 72, is_demo: bool = False, reference: str = "") -> dict:
    """Trägt alles zusammen, was die Seite je See zeigt.

    ``current`` ist die Tabelle aus :func:`cli.attach_normals` (jüngster
    Wert, 24-h-Mittel, Normalwert), ``recent`` sind die Einzelmessungen des
    Fensters, ``daily`` die Tagesreihe. Jede davon darf leer sein; ein See
    erscheint, sobald er in einer vorkommt.
    """
    current = current if current is not None else pd.DataFrame()
    recent = recent if recent is not None else pd.DataFrame()
    daily = daily if daily is not None else pd.DataFrame()

    keys: list[str] = []
    for frame in (current, recent, daily):
        if not frame.empty:
            keys += [k for k in frame["lake_key"].unique() if k in BY_KEY]
    keys = list(dict.fromkeys(keys))

    t0 = pd.Timestamp(recent["when"].min()) if not recent.empty else None
    stempel: list[pd.Timestamp] = []
    if not recent.empty:
        stempel.append(pd.Timestamp(recent["when"].max()))
    if not current.empty and "latest_at" in current:
        letzte = current["latest_at"].dropna()
        if not letzte.empty:
            stempel.append(pd.Timestamp(letzte.max()))

    seen = []
    for key in keys:
        eintrag: dict = {"key": key, "name": BY_KEY[key].name}
        punkte = recent[recent["lake_key"] == key].sort_values("when") \
            if not recent.empty else pd.DataFrame()
        zeile = current[current["lake_key"] == key] if not current.empty else pd.DataFrame()

        if not zeile.empty:
            row = zeile.iloc[0]
            latest = row.get("temp_latest")
            latest_at = row.get("latest_at")
            eintrag["jetzt"] = _rund(latest if latest is not None and pd.notna(latest)
                                     else row["temp_c"])
            eintrag["jetzt_um"] = (_minute(pd.Timestamp(latest_at))
                                   if latest_at is not None and pd.notna(latest_at)
                                   else f"{pd.Timestamp(row['date']):%Y-%m-%d}")
            eintrag["mittel_24h"] = _rund(row["temp_c"])
            eintrag["normal"] = _rund(row.get("mean"))
            eintrag["abweichung"] = _rund(row.get("anomaly"))
        elif not punkte.empty:
            # Ohne Zeile in der Sammeldatei bleibt die jüngste Einzelmessung.
            eintrag["jetzt"] = _rund(punkte["temp_c"].iloc[-1])
            eintrag["jetzt_um"] = _minute(pd.Timestamp(punkte["when"].iloc[-1]))
            eintrag["mittel_24h"] = eintrag["normal"] = eintrag["abweichung"] = None
        else:
            eintrag["jetzt"] = eintrag["jetzt_um"] = None
            eintrag["mittel_24h"] = eintrag["normal"] = eintrag["abweichung"] = None

        eintrag["trend_24h"] = trend(punkte)
        if not punkte.empty:
            eintrag["min_72h"] = _rund(punkte["temp_c"].min())
            eintrag["max_72h"] = _rund(punkte["temp_c"].max())
            eintrag["punkte"] = [
                [int((when - t0).total_seconds() // 60), round(float(temp), 2)]
                for when, temp in zip(punkte["when"], punkte["temp_c"])
            ]
        else:
            eintrag["min_72h"] = eintrag["max_72h"] = None
            eintrag["punkte"] = []

        tage = daily[daily["lake_key"] == key].sort_values("date") \
            if not daily.empty else pd.DataFrame()
        eintrag["tage"] = [
            [f"{pd.Timestamp(day):%Y-%m-%d}", round(float(temp), 2), int(n)]
            for day, temp, n in zip(tage["date"], tage["temp_c"],
                                    tage["messungen"] if "messungen" in tage
                                    else [0] * len(tage))
        ] if not tage.empty else []
        seen.append(eintrag)

    # Wärmster zuerst -- das ist die Reihenfolge, in der man die Karten liest.
    seen.sort(key=lambda s: (s["jetzt"] is None, -(s["jetzt"] or 0), s["name"]))

    newest = max(stempel) if stempel else None
    return {
        "stand": stand_iso(newest) if newest is not None else None,
        "stand_lokal": _minute(newest) if newest is not None else None,
        "quelle": source,
        "hinweis": caveat,
        "normal_demo": bool(is_demo),
        "bezug": reference,
        "schwelle_c": float(threshold),
        "fenster_h": int(hours),
        "t0": _minute(t0) if t0 is not None else None,
        "seen": seen,
    }


def write(manifest: dict, target: Path) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Kompakt: die Punktlisten sind der Grossteil, eingerückt wären sie
    # ein Vielfaches -- und niemand liest zweitausend Messwerte im Editor.
    target.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
                      + "\n", encoding="utf-8")
    return target
