#!/usr/bin/env bash
# Watches the synced OneDrive folder for CarPlay requests from the phone.
# Needs a OneDrive sync client on Linux (for example the "onedrive" client),
# syncing to ~/OneDrive.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
zaenia_need_venv
cd "$ZAENIA_ROOT"

echo
echo "ZÆNIA OneDrive CarPlay Bridge"
echo "============================="
echo

exec "$ZAENIA_PY" -m core.carplay_trigger.onedrive_bridge watch --poll 1.0
