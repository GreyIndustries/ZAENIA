#!/usr/bin/env bash
# Refreshes Google Calendar and makes a fresh CarPlay briefing with Piper.
# The zaenia-carplay-audio timer runs this on weekday afternoons.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
zaenia_need_venv
cd "$ZAENIA_ROOT"

echo
echo "ZÆNIA CarPlay briefing refresh"
echo "=============================="
echo

# WSDOT remains the temporary traffic provider (WSDOT_API_KEY in ~/.config/zaenia/env).
echo "Refreshing Google Calendar..."
if ! "$ZAENIA_PY" -m core.google_calendar_sync.google_calendar_sync_main sync --days 2; then
    echo "Google Calendar refresh failed. ZÆNIA will continue using locally available calendar data." >&2
fi

echo
echo "Generating fresh briefing with local Piper..."
"$ZAENIA_PY" -m core.carplay_audio.carplay_audio_main generate --force-traffic || {
    echo "ZÆNIA CarPlay briefing generation failed." >&2
    exit 1
}

echo
echo "CarPlay briefing refresh complete."
