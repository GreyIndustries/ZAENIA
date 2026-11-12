# Installing ZÆNIA on Windows

This is the install path for a fresh Windows 11 PC (Build Plan Phase 0, section 10 P1). It covers what the live install at `C:\Projects\ZAENIA` actually runs as of 2026-10-28. Personal data (`data/`, credentials, the voice enrollment, calendar links) is never in the repository and isn't part of a fresh install; it moves only through the encrypted export/restore.

Check the result at any point with:

```bash
.venv\Scripts\python.exe scripts\check_install.py
```

It only looks; it never downloads or installs anything.

## 1. Tools

| Tool | Version tested | Used for |
|---|---|---|
| Python | 3.13 (3.11+ works) | ZAE's server and everything in `core/` |
| Node.js | 24 | desktop and phone web builds, the Code Doctor JavaScript playground |
| Rust (cargo) | 1.99 | the Windows app (Tauri) |
| Ollama | 0.40 | ZAE's local brain |
| FFmpeg (optional) | any recent | reading audio and video files; Code Doctor can find it on PATH |

## 2. Python packages

From the project folder:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu126
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-module1.txt -r requirements-operator.txt
```

PyTorch goes first from PyTorch's own index so speaker verification gets the CUDA 12.6 build for the RTX GPU. Without an NVIDIA GPU, skip that line; the second command installs the CPU build.

`playwright` needs its browser once: `.venv\Scripts\python.exe -m playwright install msedge` (or use the installed Edge, which ZAE's browser already prefers).

## 3. Local models (not in the repository)

| Model | Where it goes | Source |
|---|---|---|
| llama3.1:8b (brain), qwen3.5:4b (photos and screen), nomic-embed-text (search index) | Ollama | `ollama pull <name>` for each |
| Vosk small English | `data/models/vosk-model-small-en-us-0.15/` | alphacephei.com/vosk/models, unzip there |
| Kokoro voice (af_heart) | `data/voices/kokoro/kokoro-v1.0.onnx` and `voices-v1.0.bin` | github.com/thewh1teagle/kokoro-onnx releases |
| Piper fallback voice | `data/voices/piper/en_US-hfc_female-medium.onnx` and `.onnx.json` | huggingface.co/rhasspy/piper-voices |
| Speaker verification (ECAPA) | `data/models/speaker_verification/ecapa_voxceleb/` | huggingface.co/speechbrain/spkrec-ecapa-voxceleb |

The voice enrollment itself is personal: re-enroll on the new PC (`core.voice_security.calibrate`) instead of copying it.

## 4. Build the apps

```bash
cd desktop && npm ci && npm run build && npm run build:web && npm run tauri build -- --no-bundle
```

Then `scripts\install_start_menu.ps1` copies the app to the Start menu, and `scripts\restart_zaenia_server.ps1` starts the server (health at `http://127.0.0.1:8766/health`).

## 5. Tests

From Git Bash in the project folder (the test modules aren't discoverable as one package, so they're listed by name):

```bash
.venv/Scripts/python.exe -m unittest $(find core scripts -name '*_test.py' | sed 's/\.py$//; s#/#.#g')
```

In `desktop`, run `node scripts/<name>.test.cjs` for each UI test. A fresh checkout skips the tests that need personal data or downloaded corpora.
