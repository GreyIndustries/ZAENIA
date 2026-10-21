"""Bundle pinned local hand tracking assets. No camera or face model is loaded."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main():
    package = ROOT/"desktop/node_modules/@mediapipe/tasks-vision"
    version = json.loads((package/"package.json").read_text())["version"]
    if version != "1.1.1": raise ValueError("Expected pinned @mediapipe/tasks-vision 1.1.1.")
    destination = ROOT/"desktop/public/handtracking"
    destination.mkdir(parents=True,exist_ok=True)
    shutil.copy2(package/"vision_bundle.js",destination/"vision_bundle.js")
    (destination/"wasm").mkdir(exist_ok=True)
    for file in (package/"wasm").iterdir():
        if file.suffix in {".js",".wasm"}: shutil.copy2(file,destination/"wasm"/file.name)
    model = destination/"hand_landmarker.task"
    if not model.exists():
        with urllib.request.urlopen(MODEL_URL,timeout=45) as response:
            raw = response.read(20*1024*1024+1)
        if len(raw)>20*1024*1024 or not raw.startswith(b"\x00\x00") and raw[:2]!=b"PK":
            raise ValueError("Unexpected hand model download.")
        model.write_bytes(raw)
    files = [{"path":file.relative_to(destination).as_posix(),"bytes":file.stat().st_size,"sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
             for file in destination.rglob("*") if file.is_file() and file.name not in {"manifest.json","worker.js"}]
    (destination/"manifest.json").write_text(json.dumps({"package":"@mediapipe/tasks-vision","version":version,
        "modelSource":MODEL_URL,"runtimeSource":"https://www.npmjs.com/package/@mediapipe/tasks-vision",
        "license":"MediaPipe runtime: Apache-2.0; model: see the official Google model card.","files":files},indent=2),encoding="utf-8")
    print(f"Bundled {len(files)} hand-only model/runtime assets locally; {sum(item['bytes'] for item in files):,} bytes.")


if __name__=="__main__": main()
