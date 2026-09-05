#!/bin/sh
# Ein Aufruf für das Handy: rechnet und legt die PNGs dort ab, wo sie die
# Galerie findet.
#
#   ./phone.sh                      # Demodaten, laufendes Jahr
#   ./phone.sh --source ehyd        # amtliche Messreihen von eHYD
#   ./phone.sh --source ehyd --lakes woerthersee --theme light
#   ./phone.sh --current none        # ohne die aktuellen Werte
#   ./phone.sh --push                # zusätzlich die Messwerte einchecken
#
# Alle Schalter werden unverändert an "python -m seetemp" durchgereicht,
# ausgenommen --out (das setzt dieses Skript) und --push.

set -eu

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

# --push aus der Argumentliste nehmen, alles andere geht an die App.
PUSH=0
ARGS=""
for arg in "$@"; do
    if [ "$arg" = "--push" ]; then
        PUSH=1
    else
        ARGS="$ARGS $arg"
    fi
done
# shellcheck disable=SC2086
set -- $ARGS

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

# Die abgelegten Messwerte einchecken -- damit rechnet auch die Auswertung
# auf GitHub damit, die den Dienst selbst nicht erreicht.
if [ "$PUSH" -eq 1 ]; then
    echo
    if ! command -v git >/dev/null 2>&1; then
        echo "git fehlt. Unter Termux: pkg install git" >&2
    elif ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo "Kein Git-Projekt -- nichts zu pushen." >&2
    elif git diff --quiet -- data/aktuell && git diff --cached --quiet -- data/aktuell \
         && [ -z "$(git ls-files --others --exclude-standard -- data/aktuell)" ]; then
        echo "Keine neuen Messwerte -- nichts einzuchecken."
    else
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        git add data/aktuell
        git commit -q -m "Messwerte vom $(date '+%d.%m.%Y, %H:%M')"
        if git push -u origin "$BRANCH"; then
            echo "Messwerte auf $BRANCH gepusht."
        else
            echo >&2
            echo "Push fehlgeschlagen. Einmalig anmelden mit:  gh auth login" >&2
            echo "(Termux: pkg install gh)" >&2
        fi
    fi
fi

echo
echo "Bilder: $OUT"
