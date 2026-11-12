"""The small part of Twilio ZAE uses: request signatures, recordings, SMS and calls.

No Twilio library is needed: the REST calls are plain HTTPS with the account SID
and auth token, and webhook signatures are checked exactly as Twilio documents
(HMAC-SHA1 over the full URL plus the sorted POST parameters).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, Callable, Mapping
from xml.sax.saxutils import escape

API = "https://api.twilio.com/2010-04-01"


def signature(token: str, url: str, params: Mapping[str, str]) -> str:
    payload = url + "".join(key + str(params[key]) for key in sorted(params))
    digest = hmac.new(token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def valid_request(token: str, url: str, params: Mapping[str, str], supplied: str | None) -> bool:
    """True only for a request Twilio signed with this account's token."""
    if not token or not supplied:
        return False
    return hmac.compare_digest(signature(token, url, params), supplied)


# ---- TwiML (the replies Twilio reads) -------------------------------------
def say(text: str) -> str:
    return f'<Say voice="Polly.Joanna-Neural">{escape(text)}</Say>'


def play(url: str) -> str:
    return f"<Play>{escape(url)}</Play>"


def record(action: str, *, max_seconds: int = 20, silence: int = 2, beep: bool = False) -> str:
    return (f'<Record action="{escape(action)}" method="POST" maxLength="{max_seconds}" timeout="{silence}" '
            f'playBeep="{"true" if beep else "false"}" trim="trim-silence"/>')


def keypad(action: str, digits: int) -> str:
    return f'<Gather input="dtmf" action="{escape(action)}" method="POST" numDigits="{digits}" timeout="8"/>'


def message(text: str) -> str:
    return f"<Message>{escape(text[:1500])}</Message>"


def response(*parts: str, hangup: bool = False) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + ("<Hangup/>" if hangup else "") + "</Response>"


# ---- REST -------------------------------------------------------------------
class TwilioClient:
    def __init__(self, account_sid: str, token: str, *, http: Callable[..., Any] | None = None):
        self.sid, self.token = account_sid, token
        self.http = http

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        if self.http is not None:
            return self.http(method, url, auth=(self.sid, self.token), **kwargs)
        import requests
        reply = requests.request(method, url, auth=(self.sid, self.token), timeout=20, **kwargs)
        reply.raise_for_status()
        return reply

    def recording_wav(self, recording_url: str) -> bytes:
        """The caller's recording as 8 kHz WAV. Only Twilio's own API host is accepted."""
        if not recording_url.startswith("https://api.twilio.com/"):
            raise ValueError("Recording is not on Twilio's API host.")
        reply = self._request("GET", recording_url + ".wav")
        return reply.content

    def delete_recording(self, recording_url: str) -> None:
        """Recordings are deleted from Twilio as soon as ZAE has heard them."""
        if recording_url.startswith("https://api.twilio.com/"):
            try:
                self._request("DELETE", recording_url + ".json")
            except Exception:
                pass

    def send_sms(self, from_number: str, to_number: str, body: str) -> Any:
        return self._request("POST", f"{API}/Accounts/{self.sid}/Messages.json",
                             data={"From": from_number, "To": to_number, "Body": body[:1500]})

    def call(self, from_number: str, to_number: str, twiml: str) -> Any:
        return self._request("POST", f"{API}/Accounts/{self.sid}/Calls.json",
                             data={"From": from_number, "To": to_number, "Twiml": twiml})

    def point_number_here(self, number: str, base_url: str) -> None:
        """Set ZAE's number to send calls and texts to this PC's /phone webhooks."""
        found = self._request("GET", f"{API}/Accounts/{self.sid}/IncomingPhoneNumbers.json",
                              params={"PhoneNumber": number}).json().get("incoming_phone_numbers") or []
        if not found:
            raise ValueError(f"{number} isn't a number on this Twilio account.")
        self._request("POST", f"{API}/Accounts/{self.sid}/IncomingPhoneNumbers/{found[0]['sid']}.json",
                      data={"VoiceUrl": base_url + "/phone/voice", "VoiceMethod": "POST",
                            "SmsUrl": base_url + "/phone/sms", "SmsMethod": "POST"})
