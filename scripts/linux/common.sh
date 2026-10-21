# Shared settings for ZÆNIA's Linux scripts (sourced, not run).
ZAENIA_ROOT="${ZAENIA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ZAENIA_PY="$ZAENIA_ROOT/.venv/bin/python"
ZAENIA_PORT=8766
ZAENIA_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/zaenia"

# Private settings (for example WSDOT_API_KEY=...) live outside the project
# folder in ~/.config/zaenia/env, readable only by you.
if [ -f "$ZAENIA_CONFIG/env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ZAENIA_CONFIG/env"
    set +a
fi

zaenia_listening() {
    if command -v ss >/dev/null 2>&1; then
        ss -ltnH "sport = :$ZAENIA_PORT" 2>/dev/null | grep -q .
        return
    fi
    (exec 3<>"/dev/tcp/127.0.0.1/$ZAENIA_PORT") 2>/dev/null
}

zaenia_need_venv() {
    if [ ! -x "$ZAENIA_PY" ]; then
        echo "ZÆNIA's Python environment is missing. Run scripts/linux/setup_linux.sh first." >&2
        exit 1
    fi
}
