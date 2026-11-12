"""Trusted-only answer-key check: executes fixed, reviewed repository references/buggy fixtures, never model replies.
The checker explicitly opts into same-account execution; it does not provide OS isolation."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bench as cb

REF = {}
def ref(name, code):
    REF[name] = code.strip("\n") + "\n"

# ---- the ten pilot tasks (already verified once) ----
ref("sum_known", r'''
def sum_known(items, key):
    vals = [i[key] for i in items if key in i and i[key] is not None]
    return (sum(vals), len(vals))
''')
ref("moving_average", r'''
def moving_average(values, window):
    return [sum(values[i:i+window]) / window for i in range(len(values) - window + 1)]
''')
ref("clip_text", r'''
def clip_text(text, limit):
    t = ' '.join(text.split())
    if limit < 1:
        return ''
    return t if len(t) <= limit else t[:limit-1] + '…'
''')
ref("merge_intervals", r'''
def merge_intervals(iv):
    out = []
    for s, e in sorted(iv):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out
''')
ref("dedupe", r'''
def dedupe(items, key):
    r = {}
    for i in items:
        r.setdefault(key(i), i)
    return list(r.values())
''')
ref("redact_keys", r'''
import re
def redact_keys(text):
    return re.sub(r'sk-[A-Za-z0-9]{20,}(?![A-Za-z0-9])', '[REDACTED]', text)
''')
ref("within_rate_limit", r'''
def within_rate_limit(ts, now, window, limit):
    return sum(1 for t in ts if now - window < t <= now) <= limit
''')
ref("parse_clock", r'''
import re
def parse_clock(text):
    m = re.fullmatch(r'\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*', text.lower())
    if not m:
        return None
    h = int(m[1]); mi = int(m[2] or 0); ap = m[3]
    if mi > 59:
        return None
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == 'pm' else 0)
    elif h > 23:
        return None
    return h * 60 + mi
''')
ref("chunk", r'''
def chunk(seq, n):
    return [seq[i:i+n] for i in range(0, len(seq), n)]
''')
ref("topo_order", r'''
def topo_order(deps):
    nodes = set(deps) | {d for v in deps.values() for d in v}
    out = []; state = {}
    def visit(n):
        if state.get(n) == 1:
            raise ValueError('cycle')
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in deps.get(n, []):
            visit(d)
        state[n] = 2
        out.append(n)
    for n in sorted(nodes):
        visit(n)
    return out
''')

# ---- new Python tasks ----
ref("normalize_phone", r'''
def normalize_phone(text):
    d = ''.join(c for c in text if c in '0123456789')
    if len(d) == 11 and d[0] == '1':
        d = d[1:]
    if len(d) == 10:
        return f'({d[:3]}) {d[3:6]}-{d[6:]}'
    return None
''')
ref("parse_duration", r'''
import re
def parse_duration(text):
    m = re.fullmatch(r'\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?\s*', text)
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s
''')
ref("slugify", r'''
import re
def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
''')
ref("roman_to_int", r'''
def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    if not s or any(c not in vals for c in s):
        raise ValueError('bad numeral')
    total = 0
    for i, c in enumerate(s):
        v = vals[c]
        if i + 1 < len(s) and vals[s[i+1]] > v:
            total -= v
        else:
            total += v
    return total
''')
ref("flatten", r'''
def flatten(nested):
    out = []
    for x in nested:
        if isinstance(x, list):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
''')
ref("rolling_max", r'''
def rolling_max(values, k):
    if k < 1 or k > len(values):
        return []
    return [max(values[i:i+k]) for i in range(len(values) - k + 1)]
''')
ref("group_by", r'''
def group_by(items, key):
    out = {}
    for it in items:
        out.setdefault(key(it), []).append(it)
    return out
''')
ref("is_balanced", r'''
def is_balanced(s):
    pairs = {')': '(', ']': '[', '}': '{'}
    st = []
    for c in s:
        if c in '([{':
            st.append(c)
        elif c in pairs:
            if not st or st.pop() != pairs[c]:
                return False
    return not st
''')
ref("calorie_balance", r'''
def calorie_balance(eaten, burned, maintenance):
    net = eaten - burned
    v = net - maintenance
    status = 'even' if abs(v) <= 50 else ('surplus' if v > 50 else 'deficit')
    return {'net': net, 'vs_maintenance': v, 'status': status}
''')
ref("next_weekday", r'''
import datetime
def next_weekday(date_iso, weekday):
    names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    d = datetime.date.fromisoformat(date_iso)
    delta = (names.index(weekday) - d.weekday()) % 7 or 7
    return (d + datetime.timedelta(days=delta)).isoformat()
''')
ref("lru_cache", r'''
from collections import OrderedDict
class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = OrderedDict()
    def get(self, key):
        if key not in self.d:
            return -1
        self.d.move_to_end(key)
        return self.d[key]
    def put(self, key, value):
        if key in self.d:
            self.d.move_to_end(key)
        self.d[key] = value
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
''')
ref("word_wrap", r'''
def word_wrap(text, width):
    lines = []; cur = ''
    for w in text.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += ' ' + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
''')
ref("bytes_human", r'''
def bytes_human(n):
    if n < 1024:
        return f'{n} B'
    units = ['KB', 'MB', 'GB']
    v = n / 1024; i = 0
    while v >= 1024 and i < 2:
        v /= 1024; i += 1
    return f'{v:.1f} {units[i]}'
''')
ref("binary_search", r'''
def binary_search(sorted_list, target):
    lo, hi = 0, len(sorted_list) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_list[mid] == target:
            return mid
        if sorted_list[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
''')
ref("parse_kv", r'''
def parse_kv(text):
    out = {}
    for part in text.split(';'):
        if not part.strip() or '=' not in part:
            continue
        k, v = part.split('=', 1)
        out[k.strip()] = v.strip()
    return out
''')
ref("median", r'''
def median(values):
    if not values:
        raise ValueError('empty')
    s = sorted(values); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
''')
ref("is_leap", r'''
def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
''')
ref("paginate", r'''
def paginate(items, page, size):
    if page < 1 or size < 1:
        return []
    start = (page - 1) * size
    return items[start:start + size]
''')
ref("count_words", r'''
def count_words(text):
    counts = {}
    for w in text.split():
        w = w.strip('.,!?;:"\'').lower()
        if w:
            counts[w] = counts.get(w, 0) + 1
    return counts
''')
ref("retry_delays", r'''
def retry_delays(attempts, base):
    return [min(30, base * 2 ** n) for n in range(attempts)]
''')

# ---- TypeScript tasks ----
ref("clamp", r'''
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
''')
ref("groupBy", r'''
function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = key(it);
    (out[k] ||= []).push(it);
  }
  return out;
}
''')
ref("formatDuration", r'''
function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
  const p = (n: number) => String(n).padStart(2, '0');
  if (h > 0) return `${h}h ${p(m)}m ${p(s)}s`;
  if (m > 0) return `${m}m ${p(s)}s`;
  return `${s}s`;
}
''')
ref("parseQuery", r'''
function parseQuery(qs: string): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};
  if (qs.startsWith('?')) qs = qs.slice(1);
  const dec = (x: string) => decodeURIComponent(x.replace(/\+/g, ' '));
  for (const part of qs.split('&')) {
    if (!part) continue;
    const i = part.indexOf('=');
    const k = dec(i < 0 ? part : part.slice(0, i));
    const v = i < 0 ? '' : dec(part.slice(i + 1));
    if (Object.prototype.hasOwnProperty.call(out, k)) {
      const cur = out[k];
      out[k] = Array.isArray(cur) ? [...cur, v] : [cur, v];
    } else {
      out[k] = v;
    }
  }
  return out;
}
''')
ref("sumFix", r'''
function sum(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0);
}
''')
ref("chunkTs", r'''
function chunk<T>(arr: T[], n: number): T[][] {
  if (n < 1) throw new RangeError('n must be at least 1');
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}
''')
ref("isPalindrome", r'''
function isPalindrome(s: string): boolean {
  const t = s.toLowerCase().replace(/[^a-z0-9]/g, '');
  return t === [...t].reverse().join('');
}
''')
ref("humanBytes", r'''
function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB'];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < 2) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${units[i]}`;
}
''')

def main():
    bad = 0
    names = [t[0] for t in cb.TASKS]
    assert len(names) == len(set(names)), "duplicate task names"
    for name, lang, kind, prompt, tests in cb.TASKS:
        if name not in REF:
            print("NO REFERENCE", name); bad += 1; continue
        # This opt-in is limited to reviewed, fixed repository fixtures, never a model answer.
        ok, why = cb.check(lang, REF[name], tests, allow_unsafe_local_execution=True)
        line = f"{lang} {kind:5} {name:18} {'ok' if ok else 'BAD: ' + why}"
        bad += not ok
        if kind == "fix":
            buggy = prompt.split("\n\n", 1)[1]
            bug_ok, bug_why = cb.check(lang, buggy, tests, allow_unsafe_local_execution=True)
            line += "   | buggy code fails the tests: " + ("YES" if not bug_ok else "NO (the bug is not caught!)")
            bad += bug_ok
        print(line, flush=True)
    by = {}
    for t in cb.TASKS:
        by[(t[1], t[2])] = by.get((t[1], t[2]), 0) + 1
    print("tasks:", len(cb.TASKS), by, "| problems:", bad)
    return int(bool(bad))

if __name__ == "__main__":
    sys.exit(main())
