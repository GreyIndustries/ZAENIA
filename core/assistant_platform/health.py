"""Small health probes and fixed recovery operations, never arbitrary commands."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import os
import shutil
import threading
import time

from core.assistant_platform.performance import COORDINATOR
from core.assistant_platform.store import ROOT

_LOCK = threading.Lock()
_HEALTH = {"at": 0., "value": None}


def inspect_health(*, refresh=False):
    with _LOCK:
        if not refresh and _HEALTH["value"] is not None and time.monotonic()-_HEALTH["at"]<10:
            return _HEALTH["value"]
    from core.brain.local_llm import check_ollama_available, get_brain_settings, _downloaded_models
    from core.api.ui_voice import service_status
    from core.brain.brain_service import _read_yaml
    settings = get_brain_settings()
    voice = _read_yaml(ROOT/"core/voice_output/voice_config.yaml")
    configured = voice.get("voice_output", {}).get("provider", "piper")
    section = voice.get(configured) or {}
    voice_path = ROOT / str(section.get("model_path") or "missing")
    voice_ready=voice_path.is_file() and (configured!='kokoro' or
        ((ROOT/str(section.get('voices_path') or 'missing')).is_file() and importlib.util.find_spec('kokoro_onnx') is not None))
    listener = service_status()
    models = _downloaded_models()
    components = [
        {"id": "api", "state": "ready", "detail": "This authenticated API request completed."},
        {"id": "model", "state": "ready" if check_ollama_available() else "offline", "detail": f"Configured: {settings['model']}",
         "downloaded": sorted(models) if models is not None else None},
        {"id": "voice", "state": "ready" if voice_ready else "missing", "detail": f"Configured voice: {configured}; checks model, voice bank and local runtime"},
        {"id": "listener", "state": "ready" if listener.get("running") else "stopped", "detail": "Verified PC voice"},
    ]
    value = {"checkedAt": datetime.now(timezone.utc).isoformat(), "components": components,
             "memoryOnlyMetrics": COORDINATOR.snapshot(), "recovery": {"model": "warm_model", "listener": "owner_voice_restart", "api": "desktop_restart"}}
    with _LOCK: _HEALTH.update(at=time.monotonic(), value=value)
    return value


def recover_model():
    import requests
    from core.brain.local_llm import active_model, get_brain_settings
    with COORDINATOR.condition:
        if COORDINATOR.foreground or COORDINATOR.background or COORDINATOR.intent:
            raise ValueError("Wait until current model work finishes before recovery.")
    settings = get_brain_settings()
    from urllib.parse import urlsplit
    parsed = urlsplit(settings["endpoint"])
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Recovery only contacts the configured local model service.")
    base = settings["endpoint"].rsplit("/",1)[0]
    response = requests.post(base+"/generate", json={"model": active_model(settings), "prompt": "", "stream": False, "keep_alive": settings["keep_alive"]}, timeout=30)
    response.raise_for_status()
    return {"status": "warmup_requested", "detail": "Local model load request completed. No service was killed or model downloaded."}


def readiness():
    from core.brain.brain_service import _read_yaml
    from core.brain.local_llm import get_brain_settings, _downloaded_models
    speech = _read_yaml(ROOT/"core/voice_listener/voice_listener_config.yaml").get("voice_listener", {}).get("speech", {})
    voice = _read_yaml(ROOT/"core/voice_output/voice_config.yaml")
    provider = (voice.get("voice_output") or {}).get("provider", "piper")
    section = voice.get(provider) or {}
    checks = [
        {"id": "python", "ok": __import__('sys').version_info >= (3,11), "detail": "Python 3.11+"},
        {"id": "desktop", "ok": (ROOT/"desktop/src-tauri/target/release/desktop.exe").is_file(), "detail": "Built Windows application"},
        {"id": "web", "ok": (ROOT/"desktop/dist-web/index.html").is_file(), "detail": "Built web application"},
        {"id": "speech_model", "ok": (ROOT/str(speech.get("model_path", "missing"))).exists(), "detail": "Local speech recognition model"},
        {"id": "voice_model", "ok": (ROOT/str(section.get("model_path", "missing"))).is_file(), "detail": f"Local {provider} model"},
        {"id": "pdf", "ok": importlib.util.find_spec("pypdf") is not None, "detail": "Local PDF text parser"},
        {"id": "disk", "ok": shutil.disk_usage(ROOT).free >= 2*1024**3, "detail": f"{round(shutil.disk_usage(ROOT).free/1024**3,1)} GiB free on current project drive"},
    ]
    if provider=='kokoro':
        checks.append({'id':'voice_bank','ok':(ROOT/str(section.get('voices_path') or 'missing')).is_file() and importlib.util.find_spec('kokoro_onnx') is not None,'detail':'Kokoro voice bank and local runtime'})
    hand_assets=ROOT/'desktop/public/handtracking'
    checks.append({'id':'hand_tracking','ok':all((hand_assets/path).is_file() for path in ['worker.js','vision_bundle.js','hand_landmarker.task','wasm/vision_wasm_internal.wasm']),'detail':'Bundled local hand model and worker'})
    models = _downloaded_models()
    settings = get_brain_settings()
    checks.append({"id": "model", "ok": models is not None and any(name in models for name in (settings["model"], settings.get("fallback_model"))), "detail": "Local language model available through Ollama"})
    for module,label in [('docx','Word documents'),('openpyxl','Excel workbooks'),('playwright','ZAE browser'),('PIL','Selected-window images'),('pywinauto','Window selection'),('psutil','Process identity checks'),('ddgs','Public web search')]:
        checks.append({'id':'operator_'+module,'ok':importlib.util.find_spec(module) is not None,'detail':label+' integration runtime'})
    from core.brain.conductor import model_for
    vision=model_for('vision')
    checks.append({'id':'vision_model','ok':models is not None and vision in models,'detail':f'Installed local {vision} vision model; no automatic download'})
    return {"checks": checks, "ready": all(item["ok"] for item in checks), "platform": os.name,
        "scope": "Readiness of this Windows assistant installation; not a bootable OS certification.",
        "manualChecks": ["Owner microphone and hands-only camera acceptance", "Selected-window vision and dedicated Edge browser acceptance", "VS Code editor focus and live phone/CarPlay handoff acceptance", "Encrypted export/restore round-trip on the destination", "Cold start and recovery on the destination SSD/PC", "Offline model, speech and document use; live weather/calendar/research need their network sources"],
        "portableExclusions": ["owner credentials and API tokens", "speaker biometric enrollment", "app launch grants", "document folder permissions", "machine-specific dependencies and downloaded language models"]}
