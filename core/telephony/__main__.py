"""Set up and use ZAE's phone line. Every command that changes or sends anything asks for the owner passkey.

  python -m core.telephony setup              connect Twilio, open the /phone path, point the number here
  python -m core.telephony status             what's set up (no secrets shown)
  python -m core.telephony pin                set the optional phone PIN (stands in for a voice check on a bad line)
  python -m core.telephony text +15551234567 "message"            text from ZAE's number
  python -m core.telephony call +15551234567 "message" [--as-me]  call and say the message (--as-me: show your number)
  python -m core.telephony disable            stop answering and close the /phone path
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import shutil
import subprocess
import sys

from core.telephony import settings

LOCAL_TARGET = "http://127.0.0.1:8766/phone"


def _owner(operation: str, payload: object) -> None:
    from core.foundation.auth.passkey import consume_fresh_auth, require_passkey
    proof = require_passkey(operation=operation, payload=payload)
    consume_fresh_auth(proof, operation=operation, payload=payload)


def _tailscale(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("tailscale") or r"C:\Program Files\Tailscale\tailscale.exe"
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=60)


def _public_base() -> str:
    try:
        name = json.loads(_tailscale("status", "--json").stdout)["Self"]["DNSName"].rstrip(".")
        return "https://" + name
    except Exception:
        return ""


def _client(config: dict) -> object:
    from core.telephony.twilio import TwilioClient
    return TwilioClient(config["account_sid"], settings.auth_token())


def setup() -> int:
    print("ZAE phone line setup. Have your Twilio Console open (twilio.com/console).\n")
    sid = input("Account SID (starts with AC): ").strip()
    token = getpass.getpass("Auth token (hidden): ").strip()
    zae = settings.normalize_number(input("ZAE's Twilio number (e.g. +15551234567): "))
    owners = [settings.normalize_number(item) for item in input("Your phone number(s), comma separated: ").split(",") if item.strip()]
    base = _public_base()
    entered = input(f"Public address for this PC [{base}]: ").strip()
    base = (entered or base).rstrip("/")
    if not (sid.startswith("AC") and len(sid) == 34 and token and owners and base.startswith("https://")):
        print("Something's missing or not in the right form. Nothing was changed.")
        return 2
    payload = {"sid": sid, "zae": zae, "owners": owners, "base": base, "token": hashlib.sha256(token.encode()).hexdigest()}
    _owner("phone.setup", payload)
    settings.store_token(token)
    previous = settings.load()
    settings.save({**previous, "enabled": True, "account_sid": sid, "zae_number": zae, "owner_numbers": owners,
                   "public_base_url": base, "pin_digits": previous.get("pin_digits", 6)})
    print("Saved. The token is sealed to your Windows account.")
    funnel = _tailscale("funnel", "--bg", "--set-path=/phone", LOCAL_TARGET)
    print("Opened only the /phone path to the internet (Tailscale Funnel)." if funnel.returncode == 0
          else "Tailscale Funnel didn't open: " + (funnel.stderr or funnel.stdout).strip()
          + "\n  Run it yourself: tailscale funnel --bg --set-path=/phone " + LOCAL_TARGET)
    try:
        _client(settings.load()).point_number_here(zae, base)
        print(f"Pointed {zae} at {base}/phone/voice and /phone/sms.")
    except Exception as error:
        print(f"Couldn't set the number's webhooks automatically ({error}).\n"
              f"  In Twilio: Phone Numbers > {zae} > Voice 'A call comes in' = Webhook {base}/phone/voice (POST);"
              f" Messaging 'A message comes in' = Webhook {base}/phone/sms (POST).")
    try:
        _client(settings.load()).send_sms(zae, owners[0], "ZAE here. My phone line is set up. Save this number.")
        print(f"Sent a test text to {owners[0]}.")
    except Exception as error:
        print(f"The test text didn't send ({error}). Trial accounts can only text verified numbers.")
    print("\nRestart ZAE's server so it starts answering: .\\scripts\\zae.ps1 restart")
    return 0


def status() -> int:
    config = settings.load()
    if not config:
        print("Not set up. Run: python -m core.telephony setup")
        return 1
    from core.telephony.pin import pin_exists
    print(json.dumps({"enabled": config.get("enabled"), "zae_number": config.get("zae_number"),
                      "owner_numbers": config.get("owner_numbers"), "public_base_url": config.get("public_base_url"),
                      "caller_id_as_you": config.get("caller_id_as_you", False), "phone_pin": pin_exists(),
                      "token_stored": settings.TOKEN_FILE.is_file()}, indent=2))
    return 0


def set_phone_pin() -> int:
    from core.telephony.pin import set_pin
    first = getpass.getpass("New phone PIN (6-8 digits, hidden): ").strip()
    if getpass.getpass("Again: ").strip() != first:
        print("They didn't match. Nothing was changed.")
        return 2
    _owner("phone.pin", {"pin": hashlib.sha256(first.encode()).hexdigest()})
    set_pin(first)
    print("Phone PIN saved (only a hash is stored).")
    return 0


def send(kind: str, number: str, text: str, as_me: bool) -> int:
    from core.telephony import twilio
    config = settings.load()
    if not settings.ready(config):
        print("Set up the phone line first: python -m core.telephony setup")
        return 1
    to = settings.normalize_number(number)
    sender = config["zae_number"]
    if as_me:
        sender = (config.get("owner_numbers") or [sender])[0]
    print(f"{'Call' if kind == 'call' else 'Text'} {to} from {sender}: {text}")
    if input("Send? (y/n) ").strip().lower() not in ("y", "yes"):
        return 1
    _owner("phone." + kind, {"to": to, "from": sender, "text": text})
    client = _client(config)
    if kind == "text":
        client.send_sms(sender, to, text)
    else:
        client.call(sender, to, twilio.response(twilio.say(text), hangup=True))
    print("Sent.")
    return 0


def disable() -> int:
    _owner("phone.disable", {})
    config = settings.load()
    if config:
        settings.save({**config, "enabled": False})
    _tailscale("funnel", "--set-path=/phone", "off")
    print("Phone line off; the /phone path is closed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ZAE's phone line")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup"); sub.add_parser("status"); sub.add_parser("pin"); sub.add_parser("disable")
    for kind in ("text", "call"):
        item = sub.add_parser(kind)
        item.add_argument("number"); item.add_argument("message")
        if kind == "call":
            item.add_argument("--as-me", action="store_true", help="Show your number (it must be a verified caller ID in Twilio).")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            return setup()
        if args.command == "status":
            return status()
        if args.command == "pin":
            return set_phone_pin()
        if args.command == "disable":
            return disable()
        return send(args.command, args.number, args.message, getattr(args, "as_me", False))
    except PermissionError as error:
        print(f"Not allowed: {error}")
        return 2
    except ValueError as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
