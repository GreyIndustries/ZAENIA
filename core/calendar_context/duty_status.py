"""Owner-selected daily duty status, separate from calendar events/configuration."""
from __future__ import annotations
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

from core.foundation.security.io import atomic_write, file_lock, protect_storage, reject_link

DUTY_FILE=Path(__file__).resolve().parents[2]/'data/duty_status/overrides.json'
LABELS={'on_duty':'On duty','off_duty':'Off duty / DONSA','class':'School / class','leave':'On leave'}
MAX_BYTES=512*1024
MAX_DATES=3660


class DutyStatusError(ValueError):pass
class DutyStatusConflict(DutyStatusError):pass


def validate_day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise DutyStatusError('Choose a date like 2026-10-18.')
    try:date.fromisoformat(value)
    except ValueError as error:raise DutyStatusError('Choose a real calendar date.') from error
    return value


def read_overrides(path=None):
    target=Path(path) if path is not None else DUTY_FILE
    reject_link(target)
    if not target.exists():return {'version':1,'revision':0,'days':{}}
    if target.stat().st_size>MAX_BYTES:raise DutyStatusError('Saved duty status exceeds its size limit.')
    try:
        with target.open('rb') as handle:raw=handle.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise DutyStatusError('Saved duty status exceeds its size limit.')
        data=json.loads(raw)
        if not isinstance(data,dict) or data.get('version')!=1 or type(data.get('revision')) is not int or data['revision']<0:raise ValueError()
        days=data.get('days')
        if not isinstance(days,dict) or len(days)>MAX_DATES:raise ValueError()
        for day,status in days.items():
            validate_day(day)
            if status not in LABELS:raise ValueError()
        return data
    except (OSError,ValueError,TypeError) as error:
        raise DutyStatusError('Saved duty status could not be read. Restore or repair its local data before editing.') from error


def set_day(day,status,revision,*,path=None):
    day=validate_day(day)
    if status is not None and (not isinstance(status,str) or status not in LABELS):raise DutyStatusError('Choose on duty, off duty/DONSA, school/class, or leave.')
    if type(revision) is not int or revision<0:raise DutyStatusError('Refresh the calendar before editing duty status.')
    target=Path(path) if path is not None else DUTY_FILE
    protect_storage(target.parent)
    with file_lock(target.with_suffix('.lock')):
        state=read_overrides(target)
        if state['revision']!=revision:raise DutyStatusConflict('Duty status changed in another window. Refresh the calendar before saving.')
        days=dict(state['days'])
        if status is None:days.pop(day,None)
        else:days[day]=status
        if len(days)>MAX_DATES:raise DutyStatusError('The duty-status collection is full; review earlier overrides.')
        updated={'version':1,'revision':revision+1,'days':days,'updatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds')}
        encoded=json.dumps(updated,ensure_ascii=False,allow_nan=False).encode('utf-8')
        if len(encoded)>MAX_BYTES:raise DutyStatusError('Saved duty status exceeds its size limit.')
        atomic_write(target,encoded)
    return {'date':day,'status':status,'label':LABELS.get(status) if status else None,'revision':updated['revision'],'source':'owner_override' if status else 'calendar'}


def apply_overrides(config):
    state=read_overrides()
    return {**config,'_owner_duty_days':state['days'],'_owner_duty_revision':state['revision']}
