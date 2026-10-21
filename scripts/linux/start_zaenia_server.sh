#!/usr/bin/env bash
# Starts the ZÆNIA API server in token mode. The zaenia-server service runs
# this at sign-in, so the phone app, CarPlay brief, chat and status work
# without the passkey; every request still needs the API token or desktop key.
# Owner features need the full server: run "server" without --unattended.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
zaenia_need_venv
cd "$ZAENIA_ROOT"

if zaenia_listening; then
    echo "ZÆNIA server is already running (port $ZAENIA_PORT)."
    exit 0
fi

exec "$ZAENIA_PY" -m core.api.server server --unattended
