#!/usr/bin/env bash
# Runs inside the zaenia-dev distrobox; started by build_desktop_app.sh.
set -euo pipefail
DESKTOP="$1" MODE="$2" WEB="$3"
if ! rpm -q webkit2gtk4.1-devel >/dev/null 2>&1; then
    echo "Installing build tools in the box (one time)..."
    sudo dnf install -y nodejs npm rust cargo gcc gcc-c++ make pkgconf-pkg-config \
        webkit2gtk4.1-devel openssl-devel curl wget file \
        libappindicator-gtk3-devel librsvg2-devel libxdo-devel
fi
cd "$DESKTOP"
# node_modules copied from Windows holds Windows-only tools: start fresh.
if [ ! -d node_modules/@tauri-apps/cli-linux-x64-gnu ]; then
    echo "Installing the app's packages (npm ci)..."
    rm -rf node_modules
    npm ci
fi
if [ "$WEB" = 1 ]; then
    npm run build:web
fi
if [ "$MODE" = dev ]; then
    exec npm run tauri dev
fi
npm run tauri build -- --no-bundle
echo
echo "Built: $DESKTOP/src-tauri/target/release/desktop"
