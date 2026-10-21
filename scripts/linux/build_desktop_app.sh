#!/usr/bin/env bash
# Builds the ZÆNIA desktop app for Linux inside a "zaenia-dev" distrobox
# (Fedora), so compilers and build libraries stay out of the system. The
# finished app runs on the system: scripts/linux/open_zaenia_app.sh.
#
#   build_desktop_app.sh          build the app
#   build_desktop_app.sh --dev    run it in development mode instead (live reload)
#   build_desktop_app.sh --web    also rebuild the phone app (desktop/dist-web)
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
BOX=zaenia-dev
MODE=build WEB=0
for arg in "$@"; do
    case "$arg" in
        --dev) MODE=dev ;;
        --web) WEB=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

command -v distrobox >/dev/null 2>&1 || { echo "distrobox is required (it's included with ZÆ OS / Aurora)." >&2; exit 1; }
# shellcheck disable=SC1091
. /etc/os-release
IMAGE="registry.fedoraproject.org/fedora-toolbox:${VERSION_ID:-latest}"
if ! distrobox list 2>/dev/null | awk -F'|' '{gsub(/ /,"",$2); print $2}' | grep -qx "$BOX"; then
    echo "Creating the $BOX build box ($IMAGE)..."
    distrobox create --yes --name "$BOX" --image "$IMAGE"
fi

distrobox enter "$BOX" -- bash "$ZAENIA_ROOT/scripts/linux/build_in_box.sh" "$ZAENIA_ROOT/desktop" "$MODE" "$WEB"

echo "Open it with: bash $ZAENIA_ROOT/scripts/linux/open_zaenia_app.sh   (or ZÆNIA in the app menu after install_zaenia_services.sh)"
