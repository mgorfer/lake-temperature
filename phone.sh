#!/bin/sh
# Ein Aufruf für das Handy: rechnet und legt die PNGs dort ab, wo sie die
# Galerie findet.
#
#   ./phone.sh                      # Demodaten, laufendes Jahr
#   ./phone.sh --source ehyd        # amtliche Messreihen von eHYD
#   ./phone.sh --source ehyd --lakes woerthersee --theme light
#   ./phone.sh --current none        # ohne die aktuellen Werte
#
# Alle Schalter werden unverändert an "python -m seetemp" durchgereicht,
# ausgenommen --out: das setzt dieses Skript.

set -eu

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

PYTHON=${PYTHON:-python3}
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python
command -v "$PYTHON" >/dev/null 2>&1 || {
    echo "Kein Python gefunden. Unter Termux: pkg install python" >&2
    exit 1
}

# Unter Termux liegt der von der Galerie sichtbare Speicher unter
# ~/storage/shared -- den gibt es aber erst nach "termux-setup-storage".
OUT="$ROOT/output"
IS_TERMUX=0
case "${PREFIX:-}" in
    *com.termux*) IS_TERMUX=1 ;;
esac

if [ "$IS_TERMUX" -eq 1 ]; then
    if [ -d "$HOME/storage/shared" ]; then
        OUT="$HOME/storage/shared/Pictures/Seetemperaturen"
    else
        echo "Hinweis: einmalig 'termux-setup-storage' ausführen und den"
        echo "Zugriff bestätigen, damit die Galerie die Bilder sieht."
        echo "Bis dahin landen sie in $OUT."
        echo
    fi
fi

# Der Dienst des Landes Kärnten antwortet Rechenzentren nicht, einem
# österreichischen Mobilfunkanschluss aber schon -- am Handy sind die
# aktuellen Werte also gerade zu holen. Eine eigene Angabe hat Vorrang.
CURRENT="--current ktn"
case " $* " in
    *" --current "*) CURRENT="" ;;
esac

# Am österreichischen Anschluss ist der Dienst erreichbar -- also gleich
# eine Kopie ablegen, damit auch die Auswertung auf GitHub damit rechnen
# kann. Schlägt es fehl, läuft der Rest trotzdem.
if [ -n "$CURRENT" ]; then
    "$PYTHON" tools/snapshot_ktn.py || echo "(kein neuer Abruf abgelegt)"
    echo
fi

mkdir -p "$OUT"
# shellcheck disable=SC2086
"$PYTHON" -m seetemp --out "$OUT" $CURRENT "$@"

# Die Galerie zeigt nur, was der Media-Scanner kennt.
if command -v termux-media-scan >/dev/null 2>&1; then
    termux-media-scan -r "$OUT" >/dev/null 2>&1 || true
    echo
    echo "Galerie aktualisiert."
elif [ "$IS_TERMUX" -eq 1 ]; then
    echo
    echo "Für die Galerie zusätzlich: pkg install termux-api"
    echo "(dann meldet dieses Skript neue Bilder automatisch an)"
fi

echo
echo "Bilder: $OUT"
