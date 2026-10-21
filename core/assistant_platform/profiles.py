"""Encrypted portable preferences and personal context, excluding machine grants.

Export/restore entry points are local-only and require fresh owner proof. Pure
codec and store helpers are also used by isolated round-trip tests.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import sqlite3

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from core.assistant_platform.store import ROOT
from core.assistant_platform.projects import validate_project
from core.assistant_platform.workspaces import validate_workspace
from core.foundation.security.io import atomic_write, reject_link

UI_KEYS = frozenset({"zaenia.shellWindows", "zaenia.workspaceLayout", "zaenia.appearance", "zaenia.speakReplies",
    "zaenia.visualMode", "zaenia.motion", "zaenia.sidebarHidden", "zaenia.coreDock"})
MAX_PROFILE = 20*1024*1024


def ui_preferences(value):
    if not isinstance(value, dict): raise ValueError("Display preferences must be an object.")
    if any(key not in UI_KEYS or not isinstance(item, str) or len(item)>100_000 for key,item in value.items()):
        raise ValueError("Only selected display preferences can travel with a profile.")
    return value


def encode_profile(payload, passphrase):
    if not isinstance(passphrase, str) or not 16 <= len(passphrase) <= 4096:
        raise ValueError("Use an encryption passphrase of at least 16 characters.")
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    if len(raw)>MAX_PROFILE: raise ValueError("Profile exceeds the 20 MiB limit.")
    salt = os.urandom(16)
    key = Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(passphrase.encode())
    envelope = {"format": "zae-profile-1", "salt": salt.hex(), "ciphertext": Fernet(base64.urlsafe_b64encode(key)).encrypt(raw).decode()}
    return json.dumps(envelope).encode()


def decode_profile(raw, passphrase):
    if len(raw)>MAX_PROFILE*2: raise ValueError("Encrypted profile is too large.")
    envelope = json.loads(raw)
    if set(envelope) != {"format", "salt", "ciphertext"} or envelope["format"] != "zae-profile-1":
        raise ValueError("Unknown profile format.")
    salt = bytes.fromhex(envelope["salt"])
    if len(salt)!=16: raise ValueError("Invalid profile salt.")
    key = Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(passphrase.encode())
    decoded = Fernet(base64.urlsafe_b64encode(key)).decrypt(envelope["ciphertext"].encode())
    if len(decoded)>MAX_PROFILE: raise ValueError("Decoded profile is too large.")
    return validate_profile(json.loads(decoded))


def validate_profile(payload):
    if not isinstance(payload, dict) or set(payload)-{"version","createdAt","memories","insights","projects","workspaces","uiSettings","continuity","notes"} or payload.get("version") not in {1,2,3}:
        raise ValueError("Unsupported profile contents.")
    from core.personal_memory.store import validate_memory
    from core.personal_memory.insights import _BLOCKED, KINDS
    for key, limit in (("memories",1000),("insights",200),("projects",2000),("workspaces",2000)):
        if not isinstance(payload.get(key), list) or len(payload[key])>limit: raise ValueError("Invalid profile collection.")
    for item in payload["memories"]:
        validate_memory(item["key"], item["value"], item["category"], "explicit_owner")
    for item in payload["insights"]:
        if not isinstance(item,dict) or item.get("kind") not in KINDS or not isinstance(item.get("text"),str) or len(item["text"])>240 or _BLOCKED.search(item["text"]):
            raise ValueError("Unsupported learned point in profile.")
    for item in payload["projects"]:
        validate_project(item)
        if not isinstance(item.get("id"),str) or len(item["id"])>64: raise ValueError("Invalid project ID.")
    for item in payload["workspaces"]:
        validate_workspace(item)
        if not isinstance(item.get("id"),str) or len(item["id"])>64: raise ValueError("Invalid workspace ID.")
        if item.get("apps"): raise ValueError("Machine-specific launch grants cannot be restored from a portable profile.")
    ui_preferences(payload.get("uiSettings", {}))
    from core.assistant_operator.service import validate_continuity
    items=payload.get('continuity',[])
    if not isinstance(items,list) or len(items)>2000: raise ValueError('Invalid continuity collection.')
    identifiers=set()
    for item in items:
        validate_continuity(item)
        if not isinstance(item.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',item['id']) or item['id'] in identifiers: raise ValueError('Invalid or repeated continuity ID.')
        identifiers.add(item['id'])
    from core.assistant_platform.notes import validate_note
    notes=payload.get('notes',[])
    if not isinstance(notes,list) or len(notes)>2000:raise ValueError('Invalid notes collection.')
    identifiers=set()
    for item in notes:
        validate_note(item)
        if not isinstance(item.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',item['id']) or item['id'] in identifiers:raise ValueError('Invalid or repeated note ID.')
        identifiers.add(item['id'])
    return payload


def capture_profile(store, *, ui=None, memory_store=None, insights=None):
    from core.personal_memory.store import DEFAULT_PATH as MEMORY_PATH, MemoryStore
    from core.personal_memory.insights import DEFAULT_PATH as INSIGHTS_PATH, InsightStore
    memories = memory_store.list(limit=1000) if memory_store is not None else MemoryStore().list(limit=1000) if MEMORY_PATH.exists() else []
    learned = insights.list(limit=200) if insights is not None else InsightStore().list(limit=200) if INSIGHTS_PATH.exists() else []
    return validate_profile({"version": 3, "createdAt": datetime.now(timezone.utc).isoformat(),
        "memories": memories, "insights": learned, "projects": store.list("project"),
        "workspaces": [{**item, "apps": []} for item in store.list("workspace")],
        "uiSettings": ui_preferences(ui or {}),"continuity":store.list('continuity'),'notes':store.list('note')})


def restore_profile(payload, store, *, mode="merge", memory_store=None, insight_store=None):
    payload = validate_profile(payload)
    if mode not in {"merge", "overwrite_conflicts"}: raise ValueError("Choose merge or overwrite_conflicts.")
    from core.personal_memory import MemoryStore
    from core.personal_memory.insights import InsightStore
    memories = memory_store or MemoryStore()
    counts = {"memories":0,"insights":0,"projects":0,"workspaces":0,"continuity":0,"notes":0,"skipped":0}
    for item in payload["memories"]:
        if memories.get(item["key"]) and mode=="merge": counts["skipped"]+=1; continue
        memories.upsert(item["key"],item["value"],item["category"]); counts["memories"]+=1
    if payload["insights"]:
        learned = insight_store or InsightStore()
        from core.foundation.security.io import file_lock
        from core.personal_memory.insights import clean_insight, MAX_INSIGHTS
        import uuid
        with file_lock(learned.path.with_suffix(".lock")):
            current=learned._read()
            for item in payload["insights"]:
                cleaned=clean_insight(item["text"],item["kind"])
                if cleaned is None: continue
                words,kind=cleaned
                known=next((row for row in current if row.get("id")==item.get("id") or row.get("text","").casefold()==words.casefold()),None)
                if known and mode=="merge": counts["skipped"]+=1; continue
                restored={"id":known["id"] if known else uuid.uuid4().hex,"text":words,"kind":kind,
                    "count":max(1,min(10000,int(item.get("count",1)))),"source":"inferred",
                    "first_seen":str(item.get("first_seen") or payload.get("createdAt") or ""),
                    "last_seen":str(item.get("last_seen") or payload.get("createdAt") or "")}
                if known: current[current.index(known)]=restored
                else: current.append(restored)
                counts["insights"]+=1
            learned._write(sorted(current,key=learned._score,reverse=True)[:MAX_INSIGHTS])
    for kind, plural, validate in (("project","projects",validate_project),("workspace","workspaces",validate_workspace)):
        for item in payload[plural]:
            if store.get(kind,item["id"]) and mode=="merge": counts["skipped"]+=1; continue
            store.put(kind,validate(item),item["id"]); counts[plural]+=1
    if payload.get("uiSettings"):
        store.put("settings", {"values": payload["uiSettings"], "needsReview": True}, "imported_display")
    from core.assistant_operator.service import validate_continuity
    for item in payload.get('continuity',[]):
        if store.get('continuity',item['id']) and mode=='merge': counts['skipped']+=1; continue
        store.put('continuity',validate_continuity(item),item['id']); counts['continuity']+=1
    from core.assistant_platform.notes import validate_note
    for item in payload.get('notes',[]):
        if store.get('note',item['id']) and mode=='merge':counts['skipped']+=1;continue
        store.put('note',{**validate_note(item),'createdAt':str(item.get('createdAt') or payload['createdAt'])},item['id']);counts['notes']+=1
    return counts


def export_to(path, payload, passphrase):
    path = Path(path)
    if not path.is_absolute() or path.suffix != ".zae-profile" or str(path).startswith(("\\\\","//")): raise ValueError("Choose an absolute local .zae-profile destination.")
    reject_link(path)
    if not path.parent.is_dir(): raise ValueError("The destination folder must already exist.")
    atomic_write(path,encode_profile(payload,passphrase),overwrite=False)
    return {"path":str(path),"bytes":path.stat().st_size}


def main():
    import argparse
    import hashlib
    from core.assistant_platform.store import PlatformStore
    from core.foundation.auth.passkey import require_passkey, consume_fresh_auth, _private_input, credential_generation
    from core.foundation.rules.engine import RuleEngine
    from core.foundation.rules.policy import assert_owner_scope
    parser = argparse.ArgumentParser(description="Local owner-authenticated portable profile tool")
    parser.add_argument("mode", choices=("export","restore"))
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    store = PlatformStore()
    request = store.get("profile_request",args.request)
    if not request or request.get("mode") != args.mode or request.get("status") != "pending":
        raise ValueError("Prepare a new profile request in the desktop app first.")
    from datetime import timedelta
    if datetime.now(timezone.utc)-datetime.fromisoformat(request["updatedAt"])>timedelta(minutes=15):
        raise ValueError("That profile request expired. Prepare a new one.")
    path = Path(request["path"])
    reject_link(path)
    if not path.is_absolute() or path.suffix!=".zae-profile" or str(path).startswith(("\\\\","//")):
        raise ValueError("Choose a local profile path.")
    binding = {"request":args.request,"path":str(path),"mode":args.mode}
    if args.mode == "restore":
        with path.open("rb") as handle: raw=handle.read(MAX_PROFILE*2+1)
        if len(raw)>MAX_PROFILE*2: raise ValueError("Profile exceeds the encrypted size limit.")
        binding["sha256"] = hashlib.sha256(raw).hexdigest()
    operation = "profile."+args.mode
    proof = require_passkey(operation=operation,payload=binding)
    assert_owner_scope(proof,operation)
    consume_fresh_auth(proof,operation=operation,payload=binding)
    owner_generation=credential_generation(); policy_generation=RuleEngine._policy_generation()
    def claim():
        if owner_generation!=credential_generation() or policy_generation!=RuleEngine._policy_generation():
            raise PermissionError("Owner credentials or policy changed during review; authenticate again.")
        assert_owner_scope(proof,operation)
        store.put("profile_request",{**request,"status":"applying"},args.request,revision=request["revision"])
    if args.mode=="export":
        payload = capture_profile(store,ui=request.get("uiSettings",{}))
        print("Encrypted export:",str(path))
        print("Counts:",{key:len(payload[key]) for key in ("memories","insights","projects","workspaces")})
        if input("Type EXPORT to write this encrypted profile: ").strip()!="EXPORT": return
        claim()
        result = export_to(path,payload,str(proof))
    else:
        backup_passphrase = _private_input("Passphrase used to encrypt this backup: ")
        payload = decode_profile(raw,backup_passphrase)
        print("Restore counts:",{key:len(payload[key]) for key in ("memories","insights","projects","workspaces")})
        print("Mode:",request.get("restoreMode","merge"),". Credentials, launch grants, models and folder permissions are excluded.")
        code = args.request[:8]
        if input(f"Type RESTORE {code} to review this exact import: ").strip()!=f"RESTORE {code}": return
        if input(f"Type APPLY {code} to confirm applying it: ").strip()!=f"APPLY {code}": return
        claim()
        # Retain an encrypted pre-restore recovery point; never a plaintext dump.
        previous = capture_profile(store)
        rollback = store.path.parent/f"before-restore-{args.request}.zae-profile"
        export_to(rollback,previous,str(proof))
        result = restore_profile(payload,store,mode=request.get("restoreMode","merge"))
        result["rollback"] = str(rollback)
    store.put("profile_request",{**request,"status":"completed","result":result},args.request,revision=request["revision"]+1)
    print("Completed:",result)


if __name__=="__main__":
    main()
