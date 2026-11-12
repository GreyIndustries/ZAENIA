"""The code-model test for the SE's 'code' workload: 38 tasks (30 Python including the ten pilot tasks, 8 TypeScript),
each run three times per model, with automatic tests. Non-thinking mode is how ZAE calls its models; qwen3:14b is also
run once in thinking mode as a reference. Generated-code execution requires explicit opt-in; neither the filters,
Python -I nor Node vm provides an OS security boundary."""
import json, pathlib, re, subprocess, sys, tempfile, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # the project folder
OUT = ROOT / "data" / "model_bench"         # results go in the private data folder, which is not committed
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import pilot_tasks as pilot

PY_HEAD = pilot.HEAD
TS_HEAD = "Write TypeScript. Reply with ONE ```ts code block that contains only the code (functions or classes defined at top level, no exports, no tests, no example calls)."
FIX = {"moving_average", "dedupe", "chunk"}
TASKS = [(n, "py", "fix" if n in FIX else "write", p, t) for n, p, t in pilot.TASKS]

def py(name, kind, text, tests, buggy=None):
    prompt = PY_HEAD + " " + text + ("\n\n" + buggy if buggy else "")
    TASKS.append((name, "py", kind, prompt, tests))

py("normalize_phone", "write", "Define normalize_phone(text): remove every character that is not a digit; if exactly 11 digits remain and the first is '1', drop that first digit; if exactly 10 digits remain return them formatted as '(AAA) BBB-CCCC', otherwise return None.",
   "assert normalize_phone('415-555-0199')=='(415) 555-0199'\nassert normalize_phone('+1 (415) 555 0199')=='(415) 555-0199'\nassert normalize_phone('555-0199') is None\nassert normalize_phone('24155550199') is None\nassert normalize_phone('') is None")
py("parse_duration", "write", "Define parse_duration(text): parse text made of one to three parts like '1h 30m', '45s', '2h' or '1h5m10s' (hours, minutes, seconds; each at most once and in that order, optional spaces between parts) into total seconds and return an integer; return None for anything else (empty text, other units, repeated or out-of-order parts).",
   "assert parse_duration('1h 30m')==5400\nassert parse_duration('45s')==45\nassert parse_duration('2h')==7200\nassert parse_duration('1h5m10s')==3910\nassert parse_duration('30m 1h') is None\nassert parse_duration('5x') is None\nassert parse_duration('') is None\nassert parse_duration('1h 1h') is None\nassert parse_duration('10m 5s')==605")
py("slugify", "write", "Define slugify(text): lowercase the text, turn every run of characters that are not letters or digits (a-z, 0-9) into a single hyphen, and strip hyphens from both ends; return '' if nothing is left.",
   "assert slugify('Hello, World!')=='hello-world'\nassert slugify('  --A  B--  ')=='a-b'\nassert slugify('!!!')==''\nassert slugify('v2.0 Release')=='v2-0-release'\nassert slugify('Café au lait')=='caf-au-lait'")
py("roman_to_int", "write", "Define roman_to_int(s): convert an uppercase Roman numeral (I V X L C D M, with the usual subtractive pairs like IV and CM) to an integer; raise ValueError if the string is empty or contains any other character.",
   "assert roman_to_int('XIV')==14\nassert roman_to_int('MCMXCIV')==1994\nassert roman_to_int('III')==3\nfor bad in ('ABC',''):\n    try:\n        roman_to_int(bad)\n        raise SystemExit('no error for '+repr(bad))\n    except ValueError:\n        pass")
py("flatten", "write", "Define flatten(nested): nested is a list that may contain lists at any depth (strings are items, not lists to flatten); return one flat list of all the non-list items in order.",
   "assert flatten([1,[2,[3,[4]],5]])==[1,2,3,4,5]\nassert flatten([])==[]\nassert flatten(['ab',['c']])==['ab','c']\nassert flatten([[],[[]]])==[]")
py("rolling_max", "write", "Define rolling_max(values, k): return the list of the maximum of every window of k consecutive values (len(values)-k+1 entries); return [] when k is less than 1 or larger than len(values).",
   "assert rolling_max([1,3,2,5,4],3)==[3,5,5]\nassert rolling_max([1,2],3)==[]\nassert rolling_max([4],1)==[4]\nassert rolling_max([1,2],0)==[]")
py("group_by", "write", "Define group_by(items, key): return a dict mapping each key(item) to the list of items with that key, in their original order.",
   "assert group_by(['apple','avocado','banana'],lambda s:s[0])=={'a':['apple','avocado'],'b':['banana']}\nassert group_by([],str)=={}")
py("is_balanced", "write", "Define is_balanced(s): return True when every (, [ and { in s is closed by the matching bracket in the right order, ignoring all other characters.",
   "assert is_balanced('([]{})') is True\nassert is_balanced('([)]') is False\nassert is_balanced('') is True\nassert is_balanced('(') is False\nassert is_balanced('a(b)c') is True\nassert is_balanced(')(') is False")
py("calorie_balance", "write", "Define calorie_balance(eaten, burned, maintenance): return a dict with 'net' = eaten - burned, 'vs_maintenance' = net - maintenance, and 'status' = 'even' when abs(vs_maintenance) <= 50, 'surplus' when vs_maintenance > 50, otherwise 'deficit'.",
   "assert calorie_balance(2000,300,1800)=={'net':1700,'vs_maintenance':-100,'status':'deficit'}\nassert calorie_balance(2400,200,2000)=={'net':2200,'vs_maintenance':200,'status':'surplus'}\nassert calorie_balance(2000,0,2050)['status']=='even'\nassert calorie_balance(2000,0,1950)['status']=='even'\nassert calorie_balance(2051,0,2000)['status']=='surplus'")
py("next_weekday", "write", "Define next_weekday(date_iso, weekday): date_iso is 'YYYY-MM-DD' and weekday is a lowercase English day name; return the ISO date string of the next date strictly after date_iso that falls on that weekday.",
   "assert next_weekday('2026-11-04','monday')=='2026-11-09'\nassert next_weekday('2026-11-04','wednesday')=='2026-11-11'\nassert next_weekday('2026-11-04','thursday')=='2026-11-05'\nassert next_weekday('2026-12-30','friday')=='2027-01-01'")
py("lru_cache", "write", "Define class LRUCache with __init__(self, capacity), get(self, key) returning the value or -1, and put(self, key, value). When a put would exceed the capacity, evict the least recently used key; both get (of an existing key) and put count as a use.",
   "c=LRUCache(2)\nc.put(1,1)\nc.put(2,2)\nassert c.get(1)==1\nc.put(3,3)\nassert c.get(2)==-1\nc.put(4,4)\nassert c.get(1)==-1\nassert c.get(3)==3\nassert c.get(4)==4")
py("word_wrap", "write", "Define word_wrap(text, width): split text on whitespace and pack the words greedily into lines of at most width characters separated by single spaces; a word longer than width gets its own line; return the list of lines.",
   "assert word_wrap('the quick brown fox',10)==['the quick','brown fox']\nassert word_wrap('a b c',1)==['a','b','c']\nassert word_wrap('abcdefghijkl mn',5)==['abcdefghijkl','mn']\nassert word_wrap('',5)==[]")
py("bytes_human", "write", "Define bytes_human(n): format a byte count with 1024-based units B, KB, MB, GB: under 1024 return f'{n} B'; otherwise divide by 1024 until the value is under 1024 or GB is reached, and return it with exactly one decimal and the unit, like '1.5 KB'.",
   "assert bytes_human(0)=='0 B'\nassert bytes_human(1023)=='1023 B'\nassert bytes_human(1024)=='1.0 KB'\nassert bytes_human(1536)=='1.5 KB'\nassert bytes_human(1048576)=='1.0 MB'\nassert bytes_human(5*1024**3)=='5.0 GB'\nassert bytes_human(2048*1024**3)=='2048.0 GB'")
py("binary_search", "write", "Define binary_search(sorted_list, target): return the index of target in the ascending list of unique numbers, or -1 when it is not there.",
   "assert binary_search([1,3,5,7,9],7)==3\nassert binary_search([1,3,5,7,9],1)==0\nassert binary_search([1,3,5,7,9],9)==4\nassert binary_search([1,3,5,7,9],4)==-1\nassert binary_search([],1)==-1")
py("parse_kv", "write", "Define parse_kv(text): text looks like 'a=1; b=two; c=' ; split it on ';', ignore blank parts, split each part on the FIRST '=' only, strip spaces around keys and values, and return a dict of strings; a part without '=' is ignored.",
   "assert parse_kv('a=1; b=two; c=')=={'a':'1','b':'two','c':''}\nassert parse_kv('x=a=b;;y')=={'x':'a=b'}\nassert parse_kv('')=={}\nassert parse_kv(' k = v ')=={'k':'v'}")
py("median", "fix", "This function should return the middle value, or the average of the two middle values when the count is even, and raise ValueError for an empty list, but it has a bug. Return the corrected function.",
   "assert median([3,1,2])==2\nassert median([4,1,3,2])==2.5\nassert median([5])==5\ntry:\n    median([])\n    raise SystemExit('no error')\nexcept ValueError:\n    pass",
   "def median(values):\n    s = sorted(values)\n    return s[len(s) // 2]")
py("is_leap", "fix", "A year is a leap year when it is divisible by 4, except years divisible by 100, unless they are also divisible by 400. This function has a bug. Return the corrected function.",
   "assert is_leap(2000) is True\nassert is_leap(1900) is False\nassert is_leap(2024) is True\nassert is_leap(2023) is False\nassert is_leap(2100) is False\nassert is_leap(2400) is True",
   "def is_leap(year):\n    return year % 4 == 0 and year % 100 != 0")
py("paginate", "fix", "Pages are numbered from 1: page 1 is the first `size` items. Return [] for a page past the end and whenever page < 1 or size < 1. This function has a bug. Return the corrected function.",
   "assert paginate([1,2,3,4,5],1,2)==[1,2]\nassert paginate([1,2,3,4,5],3,2)==[5]\nassert paginate([1,2,3,4,5],4,2)==[]\nassert paginate([1,2,3,4,5],0,2)==[]\nassert paginate([1,2,3,4,5],1,0)==[]",
   "def paginate(items, page, size):\n    start = page * size\n    return items[start:start + size]")
py("count_words", "fix", "Count words ignoring case and surrounding punctuation (. , ! ? ; : \" '), splitting on any whitespace and skipping empty words; return a dict of counts. This function has a bug. Return the corrected function.",
   "assert count_words('The cat. the dog!')=={'the':2,'cat':1,'dog':1}\nassert count_words('')=={}\nassert count_words('Hi,  hi\\nHI')=={'hi':3}\nassert count_words(\"'quoted' word\")=={'quoted':1,'word':1}",
   "def count_words(text):\n    counts = {}\n    for word in text.split(' '):\n        counts[word] = counts.get(word, 0) + 1\n    return counts")
py("retry_delays", "fix", "Exponential backoff: the delay for attempt n (counting from 0) is base * 2**n, capped at 30; return the list of delays for the given number of attempts. This function has a bug. Return the corrected function.",
   "assert retry_delays(4,1)==[1,2,4,8]\nassert retry_delays(8,1)==[1,2,4,8,16,30,30,30]\nassert retry_delays(0,1)==[]\nassert retry_delays(3,10)==[10,20,30]",
   "def retry_delays(attempts, base):\n    return [min(30, base * n) for n in range(attempts)]")

def ts(name, kind, text, tests, buggy=None):
    prompt = TS_HEAD + " " + text + ("\n\n" + buggy if buggy else "")
    TASKS.append((name, "ts", kind, prompt, tests))

ts("clamp", "write", "Define clamp(value: number, min: number, max: number): number that limits value to the range from min to max.",
   "assert.equal(clamp(5,0,3),3); assert.equal(clamp(-1,0,3),0); assert.equal(clamp(2,0,3),2);")
ts("groupBy", "write", "Define groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> that groups the items by key(item), keeping their order.",
   "assert.deepEqual(groupBy(['apple','avocado','banana'], s=>s[0]), {a:['apple','avocado'], b:['banana']}); assert.deepEqual(groupBy([], s=>String(s)), {});")
ts("formatDuration", "write", "Define formatDuration(seconds: number): string: under a minute return like '59s'; under an hour like '1m 01s'; otherwise like '1h 02m 05s' (minutes and seconds always two digits once a larger unit is shown). 0 gives '0s'.",
   "assert.equal(formatDuration(59),'59s'); assert.equal(formatDuration(61),'1m 01s'); assert.equal(formatDuration(3600),'1h 00m 00s'); assert.equal(formatDuration(3725),'1h 02m 05s'); assert.equal(formatDuration(0),'0s');")
ts("parseQuery", "write", "Define parseQuery(qs: string): Record<string, string | string[]>: qs may start with '?'; split on '&'; '+' means a space; decode with decodeURIComponent; a key that repeats becomes an array of its values in order; a key without '=' has the value ''; ignore empty parts.",
   "assert.deepEqual(parseQuery('?a=1&b=two+words&a=3'), {a:['1','3'], b:'two words'}); assert.deepEqual(parseQuery('x'), {x:''}); assert.deepEqual(parseQuery(''), {}); assert.deepEqual(parseQuery('q=%41%42&&'), {q:'AB'});")
ts("sumFix", "fix", "This function should return 0 for an empty array but it has a bug. Return the corrected function.",
   "assert.equal(sum([1,2,3]),6); assert.equal(sum([]),0);",
   "function sum(arr: number[]): number {\n  return arr.reduce((a, b) => a + b);\n}")
ts("chunkTs", "write", "Define chunk<T>(arr: T[], n: number): T[][] that splits arr into arrays of length n (the last may be shorter) and throws a RangeError when n < 1.",
   "assert.deepEqual(chunk([1,2,3,4,5],2),[[1,2],[3,4],[5]]); assert.deepEqual(chunk([],3),[]); assert.throws(()=>chunk([1],0), RangeError);")
ts("isPalindrome", "write", "Define isPalindrome(s: string): boolean that ignores case and every character that is not a letter or digit.",
   "assert.equal(isPalindrome('A man, a plan, a canal: Panama'),true); assert.equal(isPalindrome('hello'),false); assert.equal(isPalindrome(''),true); assert.equal(isPalindrome('No lemon, no melon'),true);")
ts("humanBytes", "write", "Define humanBytes(n: number): string using 1024-based units B, KB, MB, GB: under 1024 return like '512 B'; otherwise divide by 1024 until under 1024 or GB is reached and return the value with exactly one decimal and the unit, like '1.5 KB'.",
   "assert.equal(humanBytes(0),'0 B'); assert.equal(humanBytes(1023),'1023 B'); assert.equal(humanBytes(1536),'1.5 KB'); assert.equal(humanBytes(1048576),'1.0 MB'); assert.equal(humanBytes(5*1024**3),'5.0 GB');")

BANNED_PY = pilot.BANNED
BANNED_TS = re.compile(r"\b(require\s*\(|import\s|process\b|child_process|fetch\s*\(|XMLHttpRequest|eval\s*\(|Function\s*\(|globalThis|WebSocket)")
RUN_TS = str(HERE / "run_ts.cjs")

def extract(reply):
    m = re.search(r"```(?:python|py|typescript|ts|javascript|js)?\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip()

def check(lang, code, tests, *, allow_unsafe_local_execution=False):
    if not allow_unsafe_local_execution:
        return False, pilot.EXECUTION_BLOCKED
    if lang == "py":
        return pilot.check(code, tests, allow_unsafe_local_execution=True)
    if BANNED_TS.search(code):
        return False, "uses a system or network feature (not run)"
    with tempfile.TemporaryDirectory() as folder:
        c = pathlib.Path(folder) / "code.ts"; t = pathlib.Path(folder) / "tests.js"
        c.write_text(code, encoding="utf-8"); t.write_text(tests, encoding="utf-8")
        try:
            r = subprocess.run(["node", RUN_TS, pilot.UNSAFE_FLAG, str(c), str(t)], capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return False, "timed out"
        return (True, "") if r.returncode == 0 else (False, (r.stderr.strip().splitlines() or ["failed"])[0][:120])

def ask_think(model, prompt):
    import requests
    from core.brain.local_llm import get_brain_settings
    s = get_brain_settings()
    body = {"model": model, "stream": False, "think": True, "keep_alive": "10m", "options": {"temperature": 0.3, "num_ctx": 8192, "num_predict": 7000},
            "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(s["endpoint"], json=body, timeout=600); r.raise_for_status()
    return str(r.json().get("message", {}).get("content", "")).strip()

def ask_fast(model, prompt):
    from core.research.analyze import run_local
    return run_local(prompt, model=model)

def run(model, reps, think=False, *, allow_unsafe_local_execution=False):
    if not allow_unsafe_local_execution:
        raise PermissionError(pilot.EXECUTION_BLOCKED)
    label = model + ("+think" if think else "")
    call = (lambda p: ask_think(model, p)) if think else (lambda p: ask_fast(model, p))
    out = []
    try: call("Say hi.")
    except Exception as e: print(label, "load failed", e, flush=True); return out
    for rep in range(reps):
        for name, lang, kind, prompt, tests in TASKS:
            t = time.time()
            try: reply = call(prompt); err = ""
            except Exception as e: reply = ""; err = repr(e)[:80]
            secs = time.time() - t
            ok, why = check(lang, extract(reply), tests, allow_unsafe_local_execution=True) if reply else (False, err or "no reply")
            out.append({"model": label, "rep": rep, "task": name, "lang": lang, "kind": kind, "ok": ok, "why": why, "secs": round(secs, 2)})
            print(f"{label:22} r{rep} {name:18} {'PASS' if ok else 'FAIL'} {secs:6.1f}s {why}", flush=True)
    return out

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != pilot.UNSAFE_FLAG:
        raise SystemExit(pilot.EXECUTION_BLOCKED)
    args = args[1:]
    if len(args) < 3 or args[1] not in ("fast", "think"):
        raise SystemExit("usage: python -I scripts/model_bench/bench.py --allow-unsafe-local-execution <runs per task> <fast|think> <model> [<model> ...]")
    reps = int(args[0]); think = args[1] == "think"; models = args[2:]
    allr = []
    for m in models:
        allr += run(m, reps, think, allow_unsafe_local_execution=True)
        suffix = "think" if think else "fast"
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"bench_{suffix}.json").write_text(json.dumps(allr, indent=1), encoding="utf-8")
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
