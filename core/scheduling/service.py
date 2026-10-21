from __future__ import annotations
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sqlite3
import uuid

UTC = timezone.utc
TZ = ZoneInfo('America/Los_Angeles')

def instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('Supply an explicit UTC offset.')
    return dt.astimezone(UTC)

def wall(day, clock, zone=TZ):
    naive = datetime.combine(day, clock.replace(tzinfo=None))
    candidates = [naive.replace(tzinfo=zone, fold=f) for f in (0, 1)]
    valid = [d for d in candidates if d.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive]
    if not valid:
        raise ValueError('This local time does not exist because of daylight saving time.')
    if len({d.utcoffset() for d in valid}) > 1:
        raise ValueError('This local time occurs twice; supply an explicit offset.')
    return valid[0]

def validate_event(p):
    allowed = {'id','title','start','recurrence','channels'}
    if not isinstance(p, dict) or set(p) - allowed:
        raise ValueError('Unknown calendar fields.')
    title = p.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise ValueError('Use a title from 1 to 500 characters.')
    start = instant(p['start']).astimezone(TZ)
    # Recurrence uses Pacific wall time, validated on every occurrence.
    recurrence = p.get('recurrence', 'none')
    if recurrence not in ('none','daily','weekly'):
        raise ValueError('Supported recurrence: none, daily, weekly.')
    channels = p.get('channels', ['console'])
    if not isinstance(channels, list) or not channels or any(c not in ('console','email','phone') for c in channels):
        raise ValueError('Invalid delivery channel.')
    identifier = p.get('id', str(uuid.uuid4()))
    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100:
        raise ValueError('Invalid event ID.')
    return {'id':identifier,'title':title.strip(),'start':start.isoformat(),
            'recurrence':recurrence,'channels':sorted(set(channels))}

class Store:
    """Trusted storage primitive. Only registered handlers should mutate it."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db, db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, body TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(key TEXT PRIMARY KEY,event_id TEXT,revision INTEGER,due REAL,body TEXT,
              state TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,next_try REAL NOT NULL DEFAULT 0,
              lease_until REAL NOT NULL DEFAULT 0,error TEXT);
            ''')
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return closing(db)
    def put(self, p):
        with self.db() as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision FROM events WHERE id=?',(p['id'],)).fetchone()
            rev = row['revision']+1 if row else 1
            db.execute('INSERT OR REPLACE INTO events VALUES(?,?,?)',(p['id'],json.dumps(p),rev))
            db.execute("UPDATE outbox SET state='cancelled' WHERE event_id=? AND state!='sent'",(p['id'],))
        return p
    def delete(self, p):
        with self.db() as db, db:
            db.execute('DELETE FROM events WHERE id=?',(p['id'],))
            db.execute("UPDATE outbox SET state='cancelled' WHERE event_id=? AND state!='sent'",(p['id'],))
        return {'deleted':p['id']}
    def events(self):
        with self.db() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM events ORDER BY id')]
    def occurrences(self, event, lower, upper):
        start = datetime.fromisoformat(event['start'])
        step = {'none':0,'daily':1,'weekly':7}[event['recurrence']]
        day = start.date()
        if step:
            elapsed = max(0,(lower.astimezone(TZ).date()-day).days)
            day += timedelta(days=max(0,elapsed//step-1)*step)
        while day <= upper.astimezone(TZ).date():
            try:
                dt = start if day == start.date() else wall(day,start.timetz())
            except ValueError:
                # Skip ambiguous/nonexistent recurrences rather than guessing an offset.
                dt = None
            if dt and lower <= dt.astimezone(UTC) <= upper:
                yield dt.astimezone(UTC)
            if not step: break
            day += timedelta(days=step)
    def materialize(self, now):
        now = now.astimezone(UTC)
        with self.db() as db, db:
            for row in db.execute('SELECT * FROM events').fetchall():
                event = json.loads(row['body'])
                for occurrence in self.occurrences(event,now-timedelta(hours=24),now+timedelta(days=2)):
                    for minutes in (60,15,0):
                        due = occurrence-timedelta(minutes=minutes)
                        body = {'event_id':event['id'],'title':event['title'],'start':occurrence.isoformat(),'minutes':minutes}
                        for channel in event['channels']:
                            key = f"{event['id']}:{row['revision']}:{occurrence.isoformat()}:{minutes}:{channel}"
                            payload = {**body,'channel':channel,'delivery_id':key}
                            db.execute('INSERT OR IGNORE INTO outbox(key,event_id,revision,due,body) VALUES(?,?,?,?,?)',
                              (key,event['id'],row['revision'],due.timestamp(),json.dumps(payload)))
    def tick(self, now, send):
        """At-least-once delivery. Receiver should deduplicate delivery_id."""
        self.materialize(now)
        stamp = now.timestamp()
        delivered = 0
        while True:
            with self.db() as db, db:
                db.execute('BEGIN IMMEDIATE')
                # Obsolete lead alerts are suppressed; event-time catchup lasts 24 hours.
                db.execute("UPDATE outbox SET state='expired' WHERE state='pending' AND due<?",(stamp-86400,))
                rows = db.execute("SELECT * FROM outbox WHERE due<=? AND next_try<=? AND (state='pending' OR (state='sending' AND lease_until<=?)) ORDER BY due,key",(stamp,stamp,stamp)).fetchall()
                row = next((r for r in rows if r['state'] in ('pending','sending')),None)
                if not row: break
                body = json.loads(row['body'])
                event_start = instant(body['start']).timestamp()
                next_stage = event_start-900 if body['minutes']==60 else event_start
                if body['minutes'] and stamp >= next_stage:
                    db.execute("UPDATE outbox SET state='expired' WHERE key=?",(row['key'],))
                    continue
                db.execute("UPDATE outbox SET state='sending',lease_until=?,attempts=attempts+1 WHERE key=?",(stamp+120,row['key']))
            try:
                send(body)
            except Exception:
                # Never persist exception strings that could contain credentials.
                delay = min(3600,30*2**min(row['attempts'],7))
                with self.db() as db, db:
                    db.execute("UPDATE outbox SET state='pending',next_try=?,error='delivery_failed' WHERE key=? AND state='sending'",(stamp+delay,row['key']))
            else:
                with self.db() as db, db:
                    db.execute("UPDATE outbox SET state='sent',error=NULL WHERE key=? AND state='sending'",(row['key'],))
                delivered += 1
        return delivered

def validate_id(p):
    if set(p) != {'id'} or not isinstance(p['id'],str) or not 1 <= len(p['id']) <= 100:
        raise ValueError('Supply a valid event ID.')
    return dict(p)

def register(engine, store):
    def read(p):
        if p: raise ValueError('Read takes no parameters.')
        return {}
    engine.register('calendar.read',lambda p:store.events(),read)
    engine.register('calendar.write',store.put,validate_event)
    engine.register('calendar.delete',store.delete,validate_id)
