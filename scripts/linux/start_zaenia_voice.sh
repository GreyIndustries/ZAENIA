#!/usr/bin/env bash
# ZÆNIA PC voice service: always listening on your approved microphone.
# It answers only your verified voice, so it asks for your passkey when it
# starts. Leave this window open (you can minimise it). Ctrl+C stops voice.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
zaenia_need_venv
cd "$ZAENIA_ROOT"
printf '\033]0;ZAENIA Voice\007'

# Only one voice service at a time.
if pgrep -f "core\.voice_listener\.voice_listener_main" >/dev/null 2>&1; then
    echo "ZÆNIA voice is already running."
    sleep 4
    exit 0
fi

echo
echo "ZÆNIA Voice"
echo "==========="
echo "Enter your passkey below. ZÆNIA then listens for 'Zay' and answers only your voice."
echo

"$ZAENIA_PY" -m core.voice_listener.voice_listener_main start
code=$?

echo
echo "ZÆNIA voice stopped (exit $code)."
read -rp "Press Enter to close this window" _ || true
exit "$code"
