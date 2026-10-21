# ZÆNIA on Linux (ZÆ OS)

Scripts for running ZÆNIA on ZÆ OS (Aurora DX, NVIDIA Open). The Windows `.ps1` scripts in `scripts/` stay as they are.

## 1. Copy ZÆNIA from Windows
Copy `C:\Projects\ZAENIA` to `~/ZAENIA`. In Dolphin, the Windows drive shows under Devices.

**Skip:**
- `.venv`
- `.venv_broken_*`
- `node_modules`
- `desktop/node_modules`
- `desktop/src-tauri/target`
- `backups`

**Bring over:**
- `core`, `scripts`, `docs`, `desktop`
- `data`, including `data/secure`. It's encrypted with your passkey; the setup makes it readable only by you.

## 2. Set up
```
bash ~/ZAENIA/scripts/linux/setup_linux.sh
```
It does the following, and is safe to run again:
- Checks system libraries. If it adds any, restart the PC and run it again.
- Creates `.venv` (Python 3.11) and installs ZÆNIA's packages. torch is the CPU build.
- Locks down `data/secure`.
- Checks Ollama and downloads the models.
- Checks the voice models.

## 3. Start and check
```
bash ~/ZAENIA/scripts/linux/restart_zaenia_server.sh
```
Then open http://127.0.0.1:8766/app/

## 4. Owner steps (each asks for your passkey in the terminal)
```
cd ~/ZAENIA
.venv/bin/python -m core.api.server pair-desktop
.venv/bin/python -m core.foundation.foundation_main reset-approved-mic
.venv/bin/python -m core.foundation.foundation_main list-mics
.venv/bin/python -m core.foundation.foundation_main set-mic <number>
.venv/bin/python -m core.voice_security.calibrate
```

## 5. Desktop app
```
bash ~/ZAENIA/scripts/linux/build_desktop_app.sh          # build (in the zaenia-dev distrobox)
bash ~/ZAENIA/scripts/linux/build_desktop_app.sh --dev    # live development mode
bash ~/ZAENIA/scripts/linux/open_zaenia_app.sh            # open the built app
```

## 6. Background services and sign-in
```
bash ~/ZAENIA/scripts/linux/install_zaenia_services.sh --all
```

| Windows | ZÆ OS |
|---|---|
| Task "ZAENIA API Server" | `zaenia-server.service` (systemd, your user) |
| Task "ZAENIA Voice" | `~/.config/autostart/zaenia-voice.desktop`: opens the voice window 30 s after sign-in |
| Task "ZAENIA CarPlay Evening Audio" (Mon–Fri 4:46 PM) | `zaenia-carplay-audio.timer` |
| `start_carplay_bridge.ps1` | `zaenia-carplay-bridge.service` (needs a OneDrive client syncing to `~/OneDrive`) |
| `%APPDATA%\ZAENIA\desktop_approval.key` | `~/.config/zaenia/desktop_approval.key` |
| User environment variable `WSDOT_API_KEY` | `~/.config/zaenia/env` |

**Useful commands:**
```
systemctl --user status zaenia-server
journalctl --user -u zaenia-server -n 50
bash ~/ZAENIA/scripts/linux/install_zaenia_services.sh --remove
```
