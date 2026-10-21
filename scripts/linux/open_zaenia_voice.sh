#!/usr/bin/env bash
# Opens the ZÆNIA Voice window: a real terminal, so the passkey is typed there
# and never in the app. Used by the desktop app's "Start PC voice" button and
# by the sign-in item. "--delay N" waits N seconds first.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$DIR/start_zaenia_voice.sh"

if [ "${1:-}" = "--delay" ] && [ -n "${2:-}" ]; then
    sleep "$2"
fi

if command -v konsole >/dev/null 2>&1; then
    exec konsole --separate -p tabtitle="ZAENIA Voice" -e bash "$SCRIPT"
elif command -v ptyxis >/dev/null 2>&1; then
    exec ptyxis --new-window -x "bash '$SCRIPT'"
elif command -v gnome-terminal >/dev/null 2>&1; then
    exec gnome-terminal --title="ZAENIA Voice" -- bash "$SCRIPT"
elif command -v xterm >/dev/null 2>&1; then
    exec xterm -T "ZAENIA Voice" -e bash "$SCRIPT"
fi

echo "No terminal app found. Run $SCRIPT in a terminal." >&2
exit 1
