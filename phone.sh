#!/bin/sh
# Ein Aufruf für das Handy: rechnet und legt die PNGs dort ab, wo sie die
# Galerie findet.
#
#   ./phone.sh                      # Demodaten, laufendes Jahr
#   ./phone.sh --source ehyd        # amtliche Messreihen von eHYD
#   ./phone.sh --source ehyd --push # zusätzlich die Messwerte einchecken
#   ./phone.sh --current none       # ohne die aktuellen Werte
#
# Alle Schalter werden unverändert an "python -m seetemp" durchgereicht,
# ausgenommen --out (das setzt dieses Skript) und --push.
#
# Jeder Schritt wird mit Uhrzeit gemeldet und in phone.log mitgeschrieben.
# Nichts, was von aussen abhängt, läuft ohne Zeitlimit: ein Skript, das
# wortlos hängt, ist schlimmer als eines, das mit einer Meldung aufgibt.

set -eu

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

LOG="$ROOT/phone.log"
: > "$LOG"

log() {
    printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "$LOG"
}

# Führt einen Befehl mit Zeitlimit aus, wenn 'timeout' vorhanden ist.
# Rückgabe 124 heisst: Zeit abgelaufen.
mit_zeitlimit() {
    sekunden=$1
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$sekunden" "$@"
    else
        "$@"
    fi
}

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
        log "Hinweis: einmalig 'termux-setup-storage' ausführen, damit die"
        log "Galerie die Bilder sieht. Bis dahin: $OUT"
    fi
fi

# Der Dienst des Landes Kärnten antwortet Rechenzentren nicht, einem
# österreichischen Anschluss aber schon -- am Handy sind die aktuellen
# Werte also gerade zu holen. Eine eigene Angabe hat Vorrang.
CURRENT="--current ktn"
case " $* " in
    *" --current "*) CURRENT="" ;;
esac

# ------------------------------------------------------- 1: Messwerte holen
if [ -n "$CURRENT" ]; then
    log "[1/4] Aktuelle Messwerte holen"
    if mit_zeitlimit 90 "$PYTHON" tools/snapshot_ktn.py 2>&1 | tee -a "$LOG"; then
        :
    else
        log "      kein neuer Abruf abgelegt (die Auswertung läuft trotzdem)"
    fi
else
    log "[1/4] Aktuelle Messwerte übersprungen (--current angegeben)"
fi

# ------------------------------------------------------------ 2: Auswertung
log "[2/4] Auswertung rechnen"
mkdir -p "$OUT"
STATUS="$ROOT/.phone-status"
# shellcheck disable=SC2086
{ "$PYTHON" -m seetemp --out "$OUT" $CURRENT "$@"; echo $? > "$STATUS"; } 2>&1 | tee -a "$LOG"
CODE=$(cat "$STATUS" 2>/dev/null || echo 1)
rm -f "$STATUS"
if [ "$CODE" -ne 0 ]; then
    log "      Auswertung fehlgeschlagen (Code $CODE) -- siehe $LOG"
    exit "$CODE"
fi

# ---------------------------------------------------------------- 3: Galerie
# termux-media-scan wartet endlos, wenn nur das Paket termux-api installiert
# ist, die App "Termux:API" aus F-Droid aber fehlt. Deshalb Zeitlimit.
log "[3/4] Galerie benachrichtigen"
if command -v termux-media-scan >/dev/null 2>&1; then
    if mit_zeitlimit 20 termux-media-scan -r "$OUT" >/dev/null 2>&1; then
        log "      Galerie aktualisiert."
    else
        log "      termux-media-scan antwortet nicht -- übersprungen."
        log "      Meist fehlt die App \"Termux:API\" aus F-Droid; das Paket"
        log "      termux-api allein genügt nicht. Die Bilder sind trotzdem da."
    fi
elif [ "$IS_TERMUX" -eq 1 ]; then
    log "      Für die Galerie: pkg install termux-api + App \"Termux:API\" aus F-Droid"
else
    log "      übersprungen (kein Termux)"
fi

# ----------------------------------------------------------------- 4: Push
if [ "$PUSH" -eq 1 ]; then
    log "[4/4] Messwerte einchecken"
    if ! command -v git >/dev/null 2>&1; then
        log "      git fehlt. Unter Termux: pkg install git"
    elif ! git rev-parse --git-dir >/dev/null 2>&1; then
        log "      kein Git-Projekt -- nichts zu pushen."
    elif git diff --quiet -- data/aktuell && git diff --cached --quiet -- data/aktuell \
         && [ -z "$(git ls-files --others --exclude-standard -- data/aktuell)" ]; then
        log "      keine neuen Messwerte -- nichts einzuchecken."
    else
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        git add data/aktuell
        if ! git commit -q -m "Messwerte vom $(date '+%d.%m.%Y, %H:%M')" 2>&1 | tee -a "$LOG"; then
            log "      Commit fehlgeschlagen. Fehlt die Identität? Dann einmalig:"
            log "      git config --global user.name \"Dein Name\""
            log "      git config --global user.email \"du@example.com\""
        else
            log "      Push nach $BRANCH"
            # Ohne GIT_TERMINAL_PROMPT=0 wartet git auf Benutzername und
            # Passwort -- im Skript sieht das aus wie ein Hänger.
            if GIT_TERMINAL_PROMPT=0 mit_zeitlimit 120 \
                   git push -u origin "$BRANCH" 2>&1 | tee -a "$LOG"; then
                log "      gepusht."
            else
                log "      Push fehlgeschlagen oder Zeit abgelaufen."
                log "      Einmalig anmelden:  gh auth login"
                log "      (Termux: pkg install gh, dann HTTPS + Web-Browser wählen)"
                log "      Der Commit liegt lokal bereit und geht beim nächsten Mal mit."
            fi
        fi
    fi
else
    log "[4/4] Einchecken übersprungen (ohne --push)"
fi

log ""
log "Bilder:    $OUT"
log "Protokoll: $LOG"
