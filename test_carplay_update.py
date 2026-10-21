"""One isolated confirmation test, no network, credentials, calendar writes, or real voice generation."""
from __future__ import annotations
import importlib.util
import sys
import tempfile
import types
import wave
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo('America/Los_Angeles')
ROOT = Path(__file__).resolve().parent

def main():
    modules = {}
    names = {
        'core.briefing.drive_briefing': {'build_drive_briefing': lambda **kwargs: {}},
        'core.carplay_audio.carplay_audio': {'generate_piper_audio': lambda *args: None},
        'core.carplay_trigger.carplay_refresh_server': {'run_calendar_sync': lambda: {}},
    }
    for name, values in names.items():
        module = types.ModuleType(name)
        module.__dict__.update(values)
        modules[name] = module
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location('session_under_test', ROOT / 'core/carplay_trigger/briefing_session.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    def at(hour, minute=0, day=5):
        return datetime(2026, 10, day, hour, minute, tzinfo=PACIFIC)
    def audio(text, path):
        assert not any(c in text for c in '\u2013\u2014')
        with wave.open(str(path), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(22050); out.writeframes(b'\x00\x00' * 100)
    def data():
        return {'weather_location': 'JBLM',
                'weather_result': {'forecast': {'current': {'temperature_2m': 60, 'weather_code': 0}, 'current_units': {'temperature_2m': '°F'}}},
                'weather_summary': 'Weather is 60 degrees and clear.',
                'traffic_result': {'success': True}, 'traffic_summary': 'No reported traffic delays.',
                'traffic_included': True, 'traffic_window': 'afternoon',
                'personality': {'opener': 'Good morning, Grey.'},
                'calendar_context': {'date': '2026-10-05', 'status': 'work', 'events': [
                    {'title': 'Past meeting', 'time': '08:00'},
                    {'title': 'Appointment', 'time': '18:00'}]}}
    module.generate_piper_audio = audio
    module.run_calendar_sync = lambda: {'success': True, 'reason': 'Isolated test.'}
    facts = data()
    module.build_drive_briefing = lambda **kwargs: facts
    assert module.slots_for(at(11,30), {})[0] == ['first', 'lunch']
    assert module.slots_for(at(13), {'first': True})[0] == ['lunch']
    assert module.slots_for(at(13,1), {'first': True})[0] == []
    assert module.slots_for(at(16,29), {'first': True})[1] is False
    assert module.slots_for(at(16,30), {'first': True})[1] is True
    assert module.slots_for(at(17), {'first': True}) == (['evening'], False)
    assert module.answer_value('Yes.') == 'yes'
    assert module.answer_value('No, not yet.') == 'no'
    assert module.answer_value('Yes, no, maybe.') == 'unknown'
    assert module.answer_value('yesterday') == 'unknown'
    clock = [at(9)]
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        service = module.BriefingSessions(directory, clock=lambda: clock[0])
        first = service.start('first-connect')
        assert first['briefing_type'] == 'full'
        assert 'Past meeting' not in first['briefing_text']
        assert 'Appointment' in first['briefing_text']
        assert service.start('first-connect')['session_id'] == first['session_id']
        # An unplayed generation cannot consume the first full briefing.
        unplayed = service.start('unplayed')
        assert unplayed['briefing_type'] == 'full'
        service.played(first['session_id'])
        assert service.played(first['session_id'])['already_recorded']
        # Persistence across a process/service restart.
        service = module.BriefingSessions(directory, clock=lambda: clock[0])
        short = service.start('second-connect')
        assert short['briefing_type'] == 'short'
        assert short['briefing_text'] == 'No new updates.'
        service.played(short['session_id'])
        clock[0] = at(11,30)
        lunch = service.start('lunch-connect')
        assert lunch['briefing_type'] == 'full'
        service.played(lunch['session_id'])
        assert service.start('lunch-repeat')['briefing_type'] == 'short'
        # Rain starts, persists, and stops. Baselines change only after delivery.
        facts['weather_result']['forecast']['current']['weather_code'] = 61
        rain = service.start('rain-start')
        assert 'rain' in rain['briefing_text']
        assert 'rain' in service.start('rain-unplayed-retry')['briefing_text']
        service.played(rain['session_id'])
        assert service.start('rain-repeat')['briefing_text'] == 'No new updates.'
        facts['weather_result']['forecast']['current']['weather_code'] = 0
        dry = service.start('rain-stop')
        assert 'rain has stopped' in dry['briefing_text']
        service.played(dry['session_id'])
        # Small unannounced temperature changes accumulate against the spoken baseline.
        facts['weather_result']['forecast']['current']['temperature_2m'] = 63
        small = service.start('temp-small'); service.played(small['session_id'])
        facts['weather_result']['forecast']['current']['temperature_2m'] = 66
        warm = service.start('temp-big')
        assert 'warmer' in warm['briefing_text']; service.played(warm['session_id'])
        # A real traffic change is announced.
        facts['traffic_summary'] = 'A collision is causing delays.'
        traffic = service.start('traffic-change')
        assert 'collision' in traffic['briefing_text']; service.played(traffic['session_id'])
        facts['traffic_result'] = {'success': False}
        missing = service.start('traffic-unavailable')
        assert 'could not check' in missing['briefing_text']; service.played(missing['session_id'])
        facts['traffic_result'] = {'success': True}
        assert service.start('traffic-recovered')['briefing_text'] == 'No new updates.'
        clock[0] = at(16,30)
        question = service.start('departure-no')
        assert question['needs_answer'] is True
        negative = service.start(parent_id=question['session_id'], answer='No.')
        assert negative['briefing_type'] == 'short'; service.played(negative['session_id'])
        question = service.start('departure-unknown')
        unknown = service.start(parent_id=question['session_id'], answer='maybe')
        assert unknown['briefing_type'] == 'short'; service.played(unknown['session_id'])
        question = service.start('departure-yes')
        positive = service.start(parent_id=question['session_id'], answer='Yes.')
        assert positive['briefing_type'] == 'full'
        assert service.start(parent_id=question['session_id'], answer='Yes.')['session_id'] == positive['session_id']
        service.played(positive['session_id'])
        clock[0] = at(17,5)
        assert service.start('after-seventeen')['briefing_type'] == 'short'
        clock[0] = at(18,1)
        late = service.start('past-appointment')
        assert 'Appointment' not in late['briefing_text']
        clock[0] = at(0, day=6)
        facts['calendar_context']['date'] = '2026-10-06'
        assert service.start('new-day')['briefing_type'] == 'full'
        # Generation failure does not create delivery state.
        def broken(*args): raise RuntimeError('Simulated voice failure')
        module.generate_piper_audio = broken
        try:
            service.start('failed-generation')
            raise AssertionError('Failure was not raised')
        except RuntimeError:
            pass
        module.generate_piper_audio = audio
        assert service.start('after-failure')['briefing_type'] == 'full'
        # Unknown IDs, unrelated answers, and expired sessions are rejected.
        try: service.played('missing'); raise AssertionError('Missing ID accepted')
        except LookupError: pass
        try: service.start(parent_id=first['session_id'], answer='yes'); raise AssertionError('Old answer accepted')
        except ValueError: pass
    # Time and event boundaries independent of the live calendar.
    lines, _ = module.calendar_lines({'events': [{'title': 'Now', 'time': '11:30'}, {'title': 'Soon', 'time': '11:31'}, {'title': 'Unknown', 'time': ''}]}, at(11,30), False, {})
    assert len(lines) == 1 and 'Soon' in lines[0]
    # Rain forecast contrasts use actual hourly codes when supplied.
    facts = data()
    facts['weather_result']['forecast']['hourly'] = {'time': ['2026-10-05T10:00'], 'weather_code': [61]}
    weather = module.weather_snapshot(facts, at(9))
    assert weather['wet_soon'] == 'rain'
    print('PASS: daily slots, Pacific rollover, delivery acknowledgment, retry IDs, restart persistence, departure yes/no/unclear, weather contrasts, traffic changes, and past-event filtering.')
    print('This isolated test uses simulated weather, traffic, calendar, and WAV generation. Live CarPlay and Piper still require your phone/PC check.')

if __name__ == '__main__':
    main()
