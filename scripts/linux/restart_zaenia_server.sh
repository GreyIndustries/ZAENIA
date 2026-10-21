#!/usr/bin/env bash
# Restart the ZÆNIA server and check that it is listening. If it doesn't come
# up, it runs here in this window so you can see why.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
zaenia_need_venv

wait_for_server() {
    for _ in $(seq 1 40); do
        sleep 0.5
        if zaenia_listening; then
            echo
            echo "ZÆNIA server is running (port $ZAENIA_PORT)."
            return 0
        fi
    done
    return 1
}

if systemctl --user cat zaenia-server.service >/dev/null 2>&1; then
    echo "Restarting the ZÆNIA server..."
    systemctl --user restart zaenia-server.service
    wait_for_server && exit 0
    echo
    echo "The service didn't come up. Its last log lines:"
    journalctl --user -u zaenia-server.service -n 25 --no-pager
    systemctl --user stop zaenia-server.service
else
    echo "Stopping the ZÆNIA server..."
    pkill -f "core\.api\.server server" 2>/dev/null || true
    for _ in $(seq 1 20); do zaenia_listening || break; sleep 0.5; done
fi

echo
echo "Running the server here so you can see what happens."
echo "If it starts, leave this window open (Ctrl+C stops it)."
echo
cd "$ZAENIA_ROOT"
exec "$ZAENIA_PY" -m core.api.server server --unattended
