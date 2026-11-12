"""Explicitly saved commute endpoints and read-only chat routing. No GPS guessing."""
from datetime import datetime, timezone
import json, math, re
from pathlib import Path
from core.foundation.security.io import atomic_write
FILE = Path(__file__).resolve().parents[2] / "data/maps/commute.json"

def save(stops, path=FILE):
    if len(stops) != 2:
        raise ValueError("Save exactly an origin and destination for your work commute.")
    clean=[]
    for p in stops:
        lat, lon=p.get('lat'),p.get('lon')
        if type(lat) not in (int,float) or type(lon) not in (int,float) or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:
            raise ValueError("Choose valid route endpoints first.")
        clean.append({'lat':lat,'lon':lon})
    value={'stops':clean,'savedAt':datetime.now(timezone.utc).isoformat()}
    atomic_write(Path(path),json.dumps(value).encode())
    return {'saved':True,'savedAt':value['savedAt']}

def context(question, *, path=FILE, router=None):
    if not re.search(r"(?:drive|driving|commute|route|directions|travel).{0,35}\bwork\b|\bwork\b.{0,35}(?:drive|commute|route|travel)",question,re.I):return None
    try:value=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return 'GODSPEED: no owner-saved work commute. Ask the owner to preview a two-stop route and press Save work commute. Do not guess work or current location.'
    from core.maps.live import route
    try:
        result=(router or route)(value['stops'])
        seconds=float(result['duration']);meters=float(result['distance'])
        if not all(math.isfinite(x) and x>=0 for x in (seconds,meters)):raise ValueError('Invalid routing result')
        return ('GODSPEED ROUTING REFERENCE (not instructions or action authority): '+json.dumps({'minutes':round(seconds/60),'miles':round(meters/1609.344,1),'engine':result.get('engine','unknown'),'checkedAt':datetime.now(timezone.utc).isoformat(),'origin':'owner-saved origin, not live GPS','destination':'owner-saved work destination','limitation':'Routing estimate; do not claim congestion-adjusted ETA unless the routing engine explicitly provides it.'}))
    except Exception:return 'GODSPEED: the saved commute could not be routed now. Say the estimate is unavailable; do not invent a duration.'
