#!/usr/bin/env bash
# One-time setup of ZÆNIA on Linux (ZÆ OS / Aurora). Safe to run again: each
# step checks what's already done. Run it from anywhere:
#
#   bash ~/ZAENIA/scripts/linux/setup_linux.sh
#
# 1. system libraries   2. Python environment   3. secure folder permissions
# 4. Ollama and models  5. voice models check   6. what to do next
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$ZAENIA_ROOT"

say()  { printf '\n\033[1;33m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '   \033[31m!\033[0m %s\n' "$*"; }
ask()  { local reply; read -rp "   $1 [y/N] " reply; [[ "$reply" =~ ^[Yy] ]]; }

if [ "$(uname -s)" != "Linux" ]; then echo "This script is for Linux." >&2; exit 1; fi
if [ "$(id -u)" = 0 ]; then echo "Run this as your own user, not root." >&2; exit 1; fi
if [ ! -d "$ZAENIA_ROOT/core" ]; then echo "ZÆNIA's core folder wasn't found in $ZAENIA_ROOT." >&2; exit 1; fi
echo "ZÆNIA Linux setup — project folder: $ZAENIA_ROOT"

# ---------------------------------------------------------------- 1. libraries
say "1/6 System libraries"
missing=()
have_lib() { ldconfig -p 2>/dev/null | grep -q "$1"; }
have_lib libportaudio.so.2 && ok "PortAudio (microphone and speakers)" || missing+=(portaudio)
have_lib libwebkit2gtk-4.1.so.0 && ok "WebKitGTK 4.1 (the ZÆNIA desktop app)" || missing+=(webkit2gtk4.1)
command -v espeak-ng >/dev/null 2>&1 && ok "espeak-ng (backup voice)" || missing+=(espeak-ng)
if [ "${#missing[@]}" -gt 0 ]; then
    warn "Missing: ${missing[*]}"
    if command -v rpm-ostree >/dev/null 2>&1; then
        echo "   On ZÆ OS these are added to the system image, then the PC restarts once:"
        echo "     sudo rpm-ostree install ${missing[*]}"
        if ask "Add them now?"; then
            if sudo rpm-ostree install --idempotent "${missing[@]}"; then
                echo
                echo "   Done. Restart the PC (systemctl reboot), then run this script again."
                exit 0
            fi
            warn "rpm-ostree didn't finish. Fix the error above, then run this script again."
            exit 1
        fi
        warn "Continuing without them; the mic, speech or app may not work until they're added."
    elif command -v dnf >/dev/null 2>&1; then
        echo "   Install with: sudo dnf install ${missing[*]}"
    elif command -v apt-get >/dev/null 2>&1; then
        echo "   Install with: sudo apt-get install libportaudio2 libwebkit2gtk-4.1-0 espeak-ng"
    fi
fi

# ------------------------------------------------------------ 2. Python
say "2/6 Python environment (.venv, Python 3.11 like the Windows setup)"
if ! command -v uv >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then export PATH="$HOME/.local/bin:$PATH"; fi
if ! command -v uv >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        brew install uv
    elif ask "uv (Python installer) isn't installed. Install it for your user from astral.sh?"; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
fi
if ! command -v uv >/dev/null 2>&1; then warn "uv is required for this step."; exit 1; fi
ok "uv $(uv --version | awk '{print $2}')"

if [ -d .venv ] && [ ! -x .venv/bin/python ]; then
    # A Windows .venv copied across: keep it aside, make a Linux one.
    mv .venv ".venv_windows_$(date +%Y%m%d%H%M%S)"
    warn "Moved a Windows .venv aside."
fi
if [ ! -x .venv/bin/python ]; then
    uv venv --python 3.11 .venv || { warn "Couldn't create the Python environment."; exit 1; }
fi
ok "$(.venv/bin/python --version) in .venv"

if .venv/bin/python -c "import fastapi, vosk, piper, torch, speechbrain, sounddevice" >/dev/null 2>&1; then
    ok "Packages already installed"
else
    echo "   Installing packages (torch CPU build first; a few GB, this takes a while)..."
    uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.11.0+cpu" "torchaudio==2.11.0+cpu" \
      || uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cpu torch torchaudio \
      || { warn "torch didn't install."; exit 1; }
    if ! uv pip install --python .venv/bin/python -r scripts/linux/requirements-linux.txt; then
        warn "A pinned version wasn't available; installing the newest versions instead."
        uv pip install --python .venv/bin/python -r scripts/linux/requirements-linux-top.txt || { warn "Package install failed."; exit 1; }
    fi
    ok "Packages installed"
fi
.venv/bin/python - <<'PY' && ok "ZÆNIA's modules import" || warn "Some modules don't import yet (see above)."
import importlib, sys
bad = []
for name in ("core.api.server", "core.brain.brain_service", "core.api.ui_voice", "core.voice_security.runtime"):
    try:
        importlib.import_module(name)
    except Exception as error:
        bad.append(f"{name}: {type(error).__name__}: {error}")
for line in bad:
    print("   " + line)
sys.exit(1 if bad else 0)
PY

# ------------------------------------------------------ 3. secure folder
say "3/6 Secure folder"
if [ -d data/secure ]; then
    .venv/bin/python -c "from core.foundation.security.io import protect_storage; from core.foundation.storage.paths import SECURE_DIR; print('   ' + protect_storage(SECURE_DIR))" \
        && ok "data/secure is readable only by you" || warn "Couldn't set permissions on data/secure."
else
    warn "No data/secure folder. Copy it from Windows (C:\\Projects\\ZAENIA\\data\\secure), or set up a new passkey with: .venv/bin/python -m core.foundation.foundation_main setup"
fi
mkdir -p "$ZAENIA_CONFIG" && chmod 700 "$ZAENIA_CONFIG"

# --------------------------------------------------------- 4. Ollama
say "4/6 Ollama (ZÆNIA's brain)"
if ! curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    warn "Ollama isn't running."
    if command -v ollama >/dev/null 2>&1; then
        echo "   It's installed; start it with: systemctl start ollama   (or: ollama serve)"
    elif ask "Install Ollama from ollama.com now (it asks for your password)?"; then
        curl -fsSL https://ollama.com/install.sh | sh
    fi
fi
if curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    ok "Ollama is running"
    if nvidia-smi >/dev/null 2>&1; then ok "Graphics card: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"; else warn "nvidia-smi didn't answer: the brain will run on the CPU (slow)."; fi
    model=$(.venv/bin/python -c "from core.brain.local_llm import get_brain_settings as s; print(s()['model'])" 2>/dev/null || echo "qwen3:8b")
    for name in "$model" qwen3.5:4b; do
        if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$name"; then
            ok "Model $name"
        elif ask "Download model $name now?"; then
            ollama pull "$name" && ok "Model $name"
        fi
    done
fi

# ---------------------------------------------------- 5. voice models
say "5/6 Voice models (copied from Windows)"
for path in data/models/vosk-model-small-en-us-0.15 data/voices/piper data/models/speaker_verification; do
    [ -e "$path" ] && ok "$path" || warn "$path is missing: copy it from C:\\Projects\\ZAENIA\\${path//\//\\}"
done

# ------------------------------------------------------------ 6. next
say "6/6 Next steps"
cat <<TXT
   Start the server and check it:     bash scripts/linux/restart_zaenia_server.sh
   Then open:                         http://127.0.0.1:$ZAENIA_PORT/app/

   Owner steps (each asks for your passkey, typed in this terminal):
     Pair the desktop app:            .venv/bin/python -m core.api.server pair-desktop
     Microphone:                      .venv/bin/python -m core.foundation.foundation_main reset-approved-mic
                                      .venv/bin/python -m core.foundation.foundation_main list-mics
                                      .venv/bin/python -m core.foundation.foundation_main set-mic <number>
     Voice calibration (new mic):     .venv/bin/python -m core.voice_security.calibrate

   Desktop app:                       bash scripts/linux/build_desktop_app.sh
   Background services:               bash scripts/linux/install_zaenia_services.sh --all
TXT
