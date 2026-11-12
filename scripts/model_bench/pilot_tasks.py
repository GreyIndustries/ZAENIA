"""The first ten Python tasks of the SE code-model test (the pilot), with their automatic tests, and the checker that runs
a model's code against them in a fresh Python process with a time limit. Execution is disabled by default. The regex
filter and Python -I are not security isolation; opting in runs code with this account's permissions."""
import pathlib, re, subprocess, sys, tempfile

HEAD = "Write Python 3 code. Reply with ONE ```python code block that contains only the code (no tests, no explanation, no example calls)."
BUGGY = {
"moving_average": '''def moving_average(values, window):
    out = []
    for i in range(len(values) - window):
        out.append(sum(values[i:i+window]) / window)
    return out''',
"dedupe": '''def dedupe(items, key):
    result = {}
    for item in items:
        result[key(item)] = item
    return list(result.values())''',
"chunk": '''def chunk(seq, n):
    out = []
    for i in range(0, len(seq), n):
        out.append(seq[i:i+n-1])
    return out''',
}
TASKS = [
 ("sum_known", HEAD + " Define sum_known(items, key): items is a list of dicts. Return a tuple (total, known_count) where total is the sum of item[key] over the items that have the key with a value that is not None, and known_count is how many items that was.",
  "assert sum_known([{'a':1},{'a':None},{'a':2.5},{}],'a')==(3.5,2)\nassert sum_known([],'a')==(0,0)\nassert sum_known([{'b':1}],'a')==(0,0)"),
 ("moving_average", HEAD + " This function has a bug. It should return one average per full window, so len(values)-window+1 entries (an empty list when there are fewer values than the window). Return the corrected function.\n\n" + BUGGY["moving_average"],
  "assert moving_average([1,2,3,4],2)==[1.5,2.5,3.5]\nassert moving_average([1,2],2)==[1.5]\nassert moving_average([1],2)==[]\nassert moving_average([],1)==[]"),
 ("clip_text", HEAD + " Define clip_text(text, limit): collapse every run of whitespace to a single space and strip the ends. If the result is longer than limit, cut it so its total length is exactly limit and it ends with the single character '…'. If limit is less than 1 return ''.",
  "assert clip_text('  hello   world  ',20)=='hello world'\nassert clip_text('abcdefghij',5)=='abcd…'\nassert clip_text('abc',3)=='abc'\nassert clip_text('abc',0)==''\nassert len(clip_text('x'*100,10))==10"),
 ("merge_intervals", HEAD + " Define merge_intervals(intervals): merge overlapping or touching closed intervals given as (start, end) tuples in any order, and return a sorted list of tuples.",
  "assert merge_intervals([(1,3),(2,6),(8,10),(15,18)])==[(1,6),(8,10),(15,18)]\nassert merge_intervals([(1,4),(4,5)])==[(1,5)]\nassert merge_intervals([])==[]\nassert merge_intervals([(5,6),(1,2)])==[(1,2),(5,6)]"),
 ("dedupe", HEAD + " This function should keep the FIRST item for each key(item), preserving order, but it has a bug. Return the corrected function.\n\n" + BUGGY["dedupe"],
  "r=dedupe([{'id':1,'v':'a'},{'id':2,'v':'b'},{'id':1,'v':'c'}],lambda d:d['id'])\nassert r==[{'id':1,'v':'a'},{'id':2,'v':'b'}]\nassert dedupe([],len)==[]"),
 ("redact_keys", HEAD + " Define redact_keys(text): replace every token made of 'sk-' followed by 20 or more letters or digits (and nothing else) with [REDACTED]. Leave everything else unchanged.",
  "assert redact_keys('key sk-abcdefghijklmnopqrstuvwx ok')=='key [REDACTED] ok'\nassert redact_keys('sk-short')=='sk-short'\nassert redact_keys('a sk-'+'A1'*12+', b')=='a [REDACTED], b'\nassert redact_keys('sk-'+'a'*20+' sk-'+'b'*21)=='[REDACTED] [REDACTED]'"),
 ("within_rate_limit", HEAD + " Define within_rate_limit(timestamps, now, window, limit): return True when at most `limit` events fall in the half-open window (now-window, now], that is timestamps t with now-window < t <= now; timestamps is a list of numbers.",
  "assert within_rate_limit([1,2,3],3,2,2) is True\nassert within_rate_limit([1,2,3],3,2,1) is False\nassert within_rate_limit([],10,5,0) is True\nassert within_rate_limit([10],10,5,0) is False\nassert within_rate_limit([5],10,5,0) is True"),
 ("parse_clock", HEAD + " Define parse_clock(text): parse a clock time like '9:05 pm', '12 am', '23:40' or '7am' into minutes after midnight and return that integer; return None if it is not a valid time (12 am is 0, 12 pm is 720, hours above 23 or minutes above 59 are invalid, 'pm' or 'am' only with hours 1 to 12).",
  "assert parse_clock('9:05 pm')==1265\nassert parse_clock('12 am')==0\nassert parse_clock('12 pm')==720\nassert parse_clock('23:40')==1420\nassert parse_clock('7am')==420\nassert parse_clock('25:00') is None\nassert parse_clock('noon') is None\nassert parse_clock('0:00')==0\nassert parse_clock('13 pm') is None"),
 ("chunk", HEAD + " This function should split a list into lists of length n (the last one may be shorter) but it has a bug. Return the corrected function.\n\n" + BUGGY["chunk"],
  "assert chunk([1,2,3,4,5],2)==[[1,2],[3,4],[5]]\nassert chunk([],3)==[]\nassert chunk([1,2],5)==[[1,2]]"),
 ("topo_order", HEAD + " Define topo_order(deps): deps maps each task to a list of tasks it depends on. Return a list of every task (the keys and any task that only appears inside the lists) in an order where each task comes after all of its dependencies. Raise ValueError if there is a cycle.",
  "o=topo_order({'a':['b','c'],'b':['c'],'c':[]})\nassert o.index('c')<o.index('b')<o.index('a')\no=topo_order({'x':['y']})\nassert sorted(o)==['x','y'] and o.index('y')<o.index('x')\ntry:\n    topo_order({'a':['b'],'b':['a']})\n    raise SystemExit('no error on a cycle')\nexcept ValueError:\n    pass"),
]
BANNED = re.compile(r"\b(import\s+(os|sys|subprocess|socket|shutil|requests|urllib|pathlib|ctypes)|from\s+(os|sys|subprocess|socket|shutil|requests|urllib|pathlib|ctypes)\s+import|open\s*\(|__import__|eval\s*\(|exec\s*\()")
UNSAFE_FLAG = "--allow-unsafe-local-execution"
EXECUTION_BLOCKED = "Code execution is disabled; explicit --allow-unsafe-local-execution is required. This runner is not a security sandbox."

def extract(reply):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip()

def check(code, tests, *, allow_unsafe_local_execution=False):
    if not allow_unsafe_local_execution:
        return False, EXECUTION_BLOCKED
    if BANNED.search(code):
        return False, "uses a system or network module (not run)"
    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "t.py"
        path.write_text(code + "\n\n" + tests + "\n", encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(path)], capture_output=True, text=True, timeout=10, cwd=folder, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return False, "timed out"
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr.strip().splitlines() or ["failed"])[-1][:120]
