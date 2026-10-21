#!/usr/bin/env bash
# Opens the ZÆNIA desktop app (built with scripts/linux/build_desktop_app.sh).
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
APP="$ZAENIA_ROOT/desktop/src-tauri/target/release/desktop"

if [ ! -x "$APP" ]; then
    echo "The ZÆNIA desktop app isn't built yet. Run scripts/linux/build_desktop_app.sh." >&2
    exit 1
fi

# WebKit's GPU compositing can show a blank window with some NVIDIA drivers.
export WEBKIT_DISABLE_DMABUF_RENDERER="${WEBKIT_DISABLE_DMABUF_RENDERER:-1}"
exec "$APP" "$@"
