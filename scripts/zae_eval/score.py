"""Scores the checkable ZAE-Eval categories. usage: python -I scripts/zae_eval/score.py <label> [<label> ...]  (reads data/zae_eval/answers_<label>.json)"""
import json, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "data" / "zae_eval"
sys.path.insert(0, str(HERE))
from prompts import PROMPTS

def norm(text): return re.sub(r"\s+", " ", text.lower().replace("**", "")).strip()
def sentences(text): return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
def words(text): return re.findall(r"[A-Za-z0-9'’-]+", text)

def three_bullets(a):
    lines = [l for l in a.strip().splitlines() if l.strip()]
    return len(lines) == 3 and all(l.startswith("- ") and "," not in l and len(words(l[2:])) <= 12 for l in lines)
def json_name_age(a):
    t = a.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try: d = json.loads(t)
    except ValueError: return False
    return isinstance(d, dict) and set(d) == {"name", "age"}
def one_sentence_15(a):
    s = sentences(a.strip()); return len(s) == 1 and len(words(s[0])) <= 15
def five_alpha_lines(a):
    lines = [l.strip() for l in a.strip().splitlines() if l.strip()]
    return len(lines) == 5 and not any(re.match(r"^(\d|[-*•])", l) for l in lines) and [l.lower() for l in lines] == sorted(l.lower() for l in lines)
def lower_two_sentences(a):
    t = a.strip(); return t == t.lower() and len(sentences(t)) == 2
def orbit_twice_two_sentences(a):
    t = a.strip(); return len(sentences(t)) == 2 and len(re.findall(r"\borbit\b", t.lower())) == 2
FNS = {f.__name__: f for f in (three_bullets, json_name_age, one_sentence_15, five_alpha_lines, lower_two_sentences, orbit_twice_two_sentences)}

def passes(p, answer):
    kind, arg = p["check"]
    if kind == "any":
        text = norm(answer)
        # a reasoning answer may lead with the number or end with it, so look at both ends (commas in numbers ignored)
        ends = (text[:200] + " " + text[-250:]).replace(",", "") if p["cat"] == "reasoning" else text
        return any(norm(x).replace(",", "") in ends for x in arg)
    return FNS[arg](answer)

if __name__ == "__main__":
    labels = sys.argv[1:] or ["talk"]
    checkable = [p for p in PROMPTS if "check" in p]
    for label in labels:
        answers = json.loads((OUT / f"answers_{label}.json").read_text(encoding="utf-8"))
        by_cat = {}
        for p in checkable:
            a = answers.get(p["id"])
            if a is None: continue
            by_cat.setdefault(p["cat"], []).append(passes(p, a["text"]))
        total = sum(sum(v) for v in by_cat.values()); n = sum(len(v) for v in by_cat.values())
        secs = [a["secs"] for a in answers.values()]
        print(f"{label:14} {total}/{n} = {100 * total / max(1, n):.0f}%  " + "  ".join(f"{c} {sum(v)}/{len(v)}" for c, v in by_cat.items()) + f"   mean {sum(secs) / len(secs):.1f}s")
