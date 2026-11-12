"""Tables for the code-model test: pass rates, per task, failures, paired comparison, the pilot split, pass-at-3 and model combinations.
usage: python -I scripts/model_bench/analyze.py [fast|think]"""
import json, pathlib, sys, math, random, statistics as st
d = pathlib.Path(__file__).resolve().parents[2] / "data" / "model_bench"
suffix = sys.argv[1] if len(sys.argv) > 1 else "fast"
rows = json.loads((d / f"bench_{suffix}.json").read_text(encoding="utf-8"))
models = []
for r in rows:
    if r["model"] not in models: models.append(r["model"])
tasks = []
for r in rows:
    if r["task"] not in tasks: tasks.append(r["task"])
lang = {r["task"]: r["lang"] for r in rows}; kind = {r["task"]: r["kind"] for r in rows}
by = {}
for r in rows: by.setdefault((r["model"], r["task"]), []).append(r)

print("== overall (every run counts) ==")
for m in models:
    rs = [r for r in rows if r["model"] == m]
    ok = sum(r["ok"] for r in rs); secs = sum(r["secs"] for r in rs)
    reps = sorted({r["rep"] for r in rs})
    per_rep = [sum(r["ok"] for r in rs if r["rep"] == k) for k in reps]
    n_rep = len(rs) // len(reps)
    print(f"{m:22} {ok}/{len(rs)} = {100*ok/len(rs):.1f}%  per-run {per_rep} of {n_rep}   total {secs:.0f}s  mean {secs/len(rs):.2f}s  median {st.median(r['secs'] for r in rs):.2f}s  p90 {sorted(r['secs'] for r in rs)[int(.9*len(rs))]:.1f}s")

print("\n== by group (pass %) ==")
groups = {"python": lambda t: lang[t] == "py", "typescript": lambda t: lang[t] == "ts", "write new code": lambda t: kind[t] == "write", "fix a bug": lambda t: kind[t] == "fix",
          "python write": lambda t: lang[t] == "py" and kind[t] == "write", "python fix": lambda t: lang[t] == "py" and kind[t] == "fix"}
print(f"{'':16}" + "".join(f"{m:>24}" for m in models))
for g, f in groups.items():
    ts_ = [t for t in tasks if f(t)]
    line = f"{g:16}"
    for m in models:
        rs = [r for t in ts_ for r in by.get((m, t), [])]
        ok = sum(r["ok"] for r in rs)
        line += f"{ok:>6}/{len(rs):<3} {100*ok/max(1,len(rs)):5.1f}%      "
    print(line + f"  ({len(ts_)} tasks)")

print("\n== per task: passes out of runs, mean seconds ==")
print(f"{'task':18}{'lang':5}{'kind':6}" + "".join(f"{m:>24}" for m in models))
for t in tasks:
    line = f"{t:18}{lang[t]:5}{kind[t]:6}"
    for m in models:
        rs = by.get((m, t), [])
        line += f"{sum(r['ok'] for r in rs):>6}/{len(rs)}  {st.mean(r['secs'] for r in rs):5.1f}s       " if rs else " " * 24
    print(line)

print("\n== hardest tasks (fewest passes across all models) ==")
tot = sorted(tasks, key=lambda t: sum(r["ok"] for m in models for r in by.get((m, t), [])))
for t in tot[:10]:
    cells = ", ".join(f"{m.split(':')[0]}:{sum(r['ok'] for r in by.get((m, t), []))}/{len(by.get((m, t), []))}" for m in models)
    whys = {}
    for m in models:
        for r in by.get((m, t), []):
            if not r["ok"]: whys[r["why"][:60]] = whys.get(r["why"][:60], 0) + 1
    print(f"{t:18} {cells}   | {sorted(whys.items(), key=lambda kv: -kv[1])[:2]}")

print("\n== failure reasons (all models) ==")
kinds = {}
for r in rows:
    if r["ok"]: continue
    w = r["why"]
    key = "wrong answer (assertion)" if "Assertion" in w or "assert" in w.lower() else "crashed" if any(x in w for x in ("Error", "Exception")) else "not run (banned import/feature)" if "not run" in w else "timed out" if "timed out" in w else "no usable reply" if "no reply" in w else "other: " + w[:50]
    kinds.setdefault(r["model"], {}).setdefault(key, 0)
    kinds[r["model"]][key] += 1
for m in models: print(m, kinds.get(m, {}))

print("\n== paired comparison on tasks (task-level pass rate), 5000 bootstraps over tasks ==")
random.seed(7)
def rate(m, t):
    rs = by.get((m, t), []); return sum(r["ok"] for r in rs) / len(rs) if rs else 0
for a in models:
    for b in models:
        if a >= b: continue
        diffs = [rate(a, t) - rate(b, t) for t in tasks]
        boots = []
        for _ in range(5000):
            s = [random.choice(diffs) for _ in diffs]; boots.append(sum(s) / len(s))
        boots.sort()
        print(f"{a} minus {b}: mean {100*sum(diffs)/len(diffs):+.1f} points, 95% range {100*boots[125]:+.1f} to {100*boots[4874]:+.1f}   (tasks where {a} better: {sum(x>0 for x in diffs)}, worse: {sum(x<0 for x in diffs)}, same: {sum(x==0 for x in diffs)})")

print("\n== speed: mean seconds per task, same tasks ==")
for m in models:
    print(m, f"{st.mean(r['secs'] for r in rows if r['model']==m):.2f}s", "| py", f"{st.mean(r['secs'] for r in rows if r['model']==m and r['lang']=='py'):.2f}s", "| ts", f"{st.mean(r['secs'] for r in rows if r['model']==m and r['lang']=='ts'):.2f}s")

print("\n== consistency: tasks passed 3/3, 1-2/3, 0/3 ==")
for m in models:
    c = {"always": 0, "sometimes": 0, "never": 0}
    for t in tasks:
        n = sum(r["ok"] for r in by.get((m, t), [])); k = len(by.get((m, t), []))
        c["always" if n == k else "never" if n == 0 else "sometimes"] += 1
    print(m, c)


# ---- more cuts
PILOT = ["sum_known","moving_average","clip_text","merge_intervals","dedupe","redact_keys","within_rate_limit","parse_clock","chunk","topo_order"]
new = [t for t in tasks if t not in PILOT]
def passes(m, ts): return sum(r["ok"] for t in ts for r in by[(m, t)]), sum(len(by[(m, t)]) for t in ts)
print("pilot ten tasks vs the other 28:")
for m in models:
    a, an = passes(m, PILOT); b, bn = passes(m, new)
    print(f"  {m:20} pilot {a}/{an} = {100*a/an:.1f}%   other 28: {b}/{bn} = {100*b/bn:.1f}%")
print("solved at least once in 3 runs (pass@3):")
for m in models:
    s = [t for t in tasks if any(r["ok"] for r in by[(m, t)])]
    print(f"  {m:20} {len(s)}/{len(tasks)} = {100*len(s)/len(tasks):.1f}%   never solved: {[t for t in tasks if t not in s]}")
print("solved at least once by ANY of the models in the group:")
for combo in ([models[:2], [models[0], models[2]], [models[1], models[2]], models] if len(models) >= 3 else [models]):
    s = [t for t in tasks if any(r["ok"] for m in combo for r in by[(m, t)])]
    print(f"  {' + '.join(c.split(':')[0] for c in combo):40} {len(s)}/{len(tasks)}   not solved: {[t for t in tasks if t not in s]}")
print("single-run majority (2 of 3) solved:")
for m in models:
    s = [t for t in tasks if sum(r["ok"] for r in by[(m, t)]) >= 2]
    print(f"  {m:20} {len(s)}/{len(tasks)}")
print("time: mean, median, p90, max and share from the slowest 3 tasks")
for m in models:
    rs = [r["secs"] for r in rows if r["model"] == m]
    tot = sum(rs)
    per = sorted(((sum(r["secs"] for r in by[(m, t)]), t) for t in tasks), reverse=True)[:3]
    print(f"  {m:20} mean {st.mean(rs):.2f} median {st.median(rs):.2f} max {max(rs):.1f}s  slowest3 {[ (t, round(s)) for s, t in per]} = {100*sum(s for s,_ in per)/tot:.0f}% of total {tot:.0f}s")
print("excluding parse_clock and parse_duration:")
for m in models:
    rs = [r["secs"] for r in rows if r["model"] == m and r["task"] not in ("parse_clock", "parse_duration")]
    print(f"  {m:20} mean {st.mean(rs):.2f}s over {len(rs)} runs")
# agreement between rep runs: how often did the same task give a different result in the 3 runs
print("tasks with mixed results across the 3 runs (not 0/3 or 3/3):")
for m in models:
    print(f"  {m:20} {[(t, sum(r['ok'] for r in by[(m, t)])) for t in tasks if 0 < sum(r['ok'] for r in by[(m, t)]) < 3]}")
