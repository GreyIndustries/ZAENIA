#!/usr/bin/env bash
# Installs ZÆNIA's background services for your user (systemd) and her
# sign-in items. Run it again any time; it replaces what it installed before.
#
#   install_zaenia_services.sh                  server only
#   install_zaenia_services.sh --all            everything below
#   --carplay        weekday CarPlay briefing (4:46 PM, Mon-Fri)
#   --carplay-bridge phone CarPlay requests through OneDrive (needs a OneDrive client)
#   --voice-at-login open the ZÆNIA Voice window 30 s after sign-in
#   --app-at-login   open the ZÆNIA app at sign-in
#   --remove         stop and remove everything this script installs
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
SRC="$ZAENIA_ROOT/scripts/linux/systemd"

carplay=0 bridge=0 voice=0 app=0 remove=0
for arg in "$@"; do
    case "$arg" in
        --all) carplay=1 bridge=1 voice=1 app=1 ;;
        --carplay) carplay=1 ;;
        --carplay-bridge) bridge=1 ;;
        --voice-at-login) voice=1 ;;
        --app-at-login) app=1 ;;
        --remove) remove=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

render() {  # template -> destination, with this project's folder filled in
    mkdir -p "$(dirname "$2")"
    sed "s|@ROOT@|$ZAENIA_ROOT|g" "$1" > "$2"
}

if [ "$remove" = 1 ]; then
    systemctl --user disable --now zaenia-server.service zaenia-carplay-audio.timer zaenia-carplay-bridge.service 2>/dev/null || true
    rm -f "$UNITS"/zaenia-server.service "$UNITS"/zaenia-carplay-audio.service "$UNITS"/zaenia-carplay-audio.timer \
          "$UNITS"/zaenia-carplay-bridge.service "$AUTOSTART"/zaenia-voice.desktop "$AUTOSTART"/zaenia.desktop
    systemctl --user daemon-reload
    echo "ZÆNIA services and sign-in items removed. The app shortcut in the menu stays."
    exit 0
fi

zaenia_need_venv
chmod +x "$ZAENIA_ROOT"/scripts/linux/*.sh
mkdir -p "$ZAENIA_CONFIG"
chmod 700 "$ZAENIA_CONFIG"
if [ ! -f "$ZAENIA_CONFIG/env" ]; then
    printf '# Private settings for ZÆNIA services (KEY=value per line).\n# WSDOT_API_KEY=\n' > "$ZAENIA_CONFIG/env"
fi
chmod 600 "$ZAENIA_CONFIG/env"

# The server: starts at sign-in, restarts if it stops unexpectedly.
render "$SRC/zaenia-server.service" "$UNITS/zaenia-server.service"
if [ "$carplay" = 1 ]; then
    render "$SRC/zaenia-carplay-audio.service" "$UNITS/zaenia-carplay-audio.service"
    render "$SRC/zaenia-carplay-audio.timer" "$UNITS/zaenia-carplay-audio.timer"
fi
if [ "$bridge" = 1 ]; then
    render "$SRC/zaenia-carplay-bridge.service" "$UNITS/zaenia-carplay-bridge.service"
fi
systemctl --user daemon-reload

# A port-8766 server started by hand would block the service.
if zaenia_listening && ! systemctl --user is-active --quiet zaenia-server.service; then
    pkill -f "core\.api\.server server" 2>/dev/null || true
    sleep 2
fi
systemctl --user enable --now zaenia-server.service
[ "$carplay" = 1 ] && systemctl --user enable --now zaenia-carplay-audio.timer
[ "$bridge" = 1 ] && systemctl --user enable --now zaenia-carplay-bridge.service

# The app in the menu (always), and the sign-in items you asked for.
render "$SRC/zaenia.desktop" "$APPS/zaenia.desktop"
[ "$voice" = 1 ] && render "$SRC/zaenia-voice.desktop" "$AUTOSTART/zaenia-voice.desktop"
[ "$app" = 1 ] && render "$SRC/zaenia.desktop" "$AUTOSTART/zaenia.desktop"

for _ in $(seq 1 40); do zaenia_listening && break; sleep 0.5; done
echo
if zaenia_listening; then
    echo "ZÆNIA server: running (port $ZAENIA_PORT), starts at every sign-in."
else
    echo "ZÆNIA server: installed, but not listening yet. Check: journalctl --user -u zaenia-server -n 40"
fi
[ "$carplay" = 1 ] && echo "CarPlay briefing: weekdays at 4:46 PM (next: $(systemctl --user list-timers zaenia-carplay-audio.timer --no-legend | awk '{print $1, $2, $3}'))"
[ "$bridge" = 1 ] && echo "CarPlay bridge: watching ~/OneDrive."
[ "$voice" = 1 ] && echo "ZÆNIA Voice window: opens 30 s after sign-in."
[ "$app" = 1 ] && echo "ZÆNIA app: opens at sign-in."
echo "Private settings: $ZAENIA_CONFIG/env"
