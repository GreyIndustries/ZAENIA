"""Conservative offline proposals. Ambiguous times require clarification."""
import re
from datetime import datetime, timedelta, time
from core.scheduling.service import TZ, UTC, wall, validate_event

def propose(text, now=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    pattern = (r'^(?:remind me(?: to)?|schedule)\s+(.+?)\s+'
               r'(today|tomorrow|\d{4}-\d{2}-\d{2})\s+at\s+'
               r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s+(daily|weekly))?\.?$')
    m = re.fullmatch(pattern,text.strip(),re.I)
    if not m:
        return {'needs_clarification':True,'reason':'Use: remind me to bring the radio tomorrow at 7 PM. Include a date and explicit time.'}
    title,day,hour,minute,ampm,recurrence = m.groups()
    hour,minute = int(hour),int(minute or 0)
    if ampm:
        if not 1 <= hour <= 12: raise ValueError('Invalid 12-hour time.')
        hour = hour%12 + (12 if ampm.lower()=='pm' else 0)
    elif ':' not in m.group(0) and hour < 13:
        return {'needs_clarification':True,'reason':'Specify AM/PM or a 24-hour HH:MM time.'}
    target = now.date() + timedelta(days=1 if day.lower()=='tomorrow' else 0) if day.lower() in ('today','tomorrow') else datetime.fromisoformat(day).date()
    try:
        start = wall(target,time(hour,minute))
    except ValueError as e:
        return {'needs_clarification':True,'reason':str(e)}
    if start.astimezone(UTC) <= now.astimezone(UTC):
        return {'needs_clarification':True,'reason':'That time has passed. Supply a future date.'}
    return {'needs_clarification':False,'proposal':validate_event({'title':title,'start':start.isoformat(),'recurrence':recurrence or 'none'})}
