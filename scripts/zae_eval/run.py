"""Runs ZAE-Eval prompts on a local model. usage: python -I scripts/zae_eval/run.py <label> <model> <fast|think> [cats comma list]
Answers go to data/zae_eval/answers_<label>.json (the private data folder, not committed)."""
import json, pathlib, sys, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "data" / "zae_eval"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
from prompts import PROMPTS
import requests

def ask(model, question, think):
    from core.brain.local_llm import get_brain_settings
    s = get_brain_settings()
    body = {"model": model, "stream": False, "think": think, "keep_alive": "10m",
            "options": {"temperature": 0.3, "num_ctx": 8192, **({"num_predict": 6000} if think else {})},
            "messages": [{"role": "user", "content": question}]}
    r = requests.post(s["endpoint"], json=body, timeout=600); r.raise_for_status()
    return str(r.json().get("message", {}).get("content", "")).strip()

if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[3] not in ("fast", "think"):
        sys.exit("usage: python -I scripts/zae_eval/run.py <label> <model> <fast|think> [categories]")
    label, model, mode = sys.argv[1], sys.argv[2], sys.argv[3]
    cats = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"answers_{label}.json"
    answers = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    ask(model, "Say hi.", False)
    for p in PROMPTS:
        if cats and p["cat"] not in cats: continue
        t = time.time()
        try: text = ask(model, p["q"], mode == "think")
        except Exception as e: text = ""
        answers[p["id"]] = {"text": text, "secs": round(time.time() - t, 1)}
        print(f"{label} {p['id']} {answers[p['id']]['secs']}s", flush=True)
        path.write_text(json.dumps(answers, indent=1), encoding="utf-8")
