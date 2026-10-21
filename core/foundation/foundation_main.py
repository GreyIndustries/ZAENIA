"""One foundation CLI shared by main.py, start.py and foundation_main.py."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from cryptography.fernet import InvalidToken
from core.foundation.auth.passkey import create_passkey, passkey_exists, require_passkey, payload_digest
from core.foundation.lifecycle import activation_binding, activate_foundation, backup_binding, export_policy_backup, restore_binding, restore_policy_backup
from core.foundation.moral_code.engine import MoralCase, evaluate_moral_case
from core.foundation.moral_code.vault import load_policy, update_notes
from core.foundation.moral_code.scripture_context import Corpus, update_context
from core.foundation.rules.engine import evaluate_operation, delete_rule, disable_rule
from core.foundation.rules.models import create_rule, OPERATIONS
from core.foundation.rules.vault import add_rule, list_rules
from core.foundation.rules.policy import assert_owner_scope
from core.foundation.security.audit import audit
from core.foundation.security.io import protect_storage
from core.foundation.storage.paths import AUDIT_FILE, SECURE_DIR, PROJECT_ROOT

def print_json(value) -> None:
    print(json.dumps(value,ensure_ascii=False,indent=2))

def owner_read(operation: str) -> str:
    from core.foundation.auth.passkey import consume_fresh_auth
    proof=require_passkey(operation=operation)
    consume_fresh_auth(proof,operation=operation)
    assert_owner_scope(proof,operation)
    return proof

def _json_file(path: Path):
    if path.stat().st_size > 65536:
        raise ValueError("Input document exceeds 64 KiB.")
    return json.loads(path.read_text(encoding="utf-8-sig"))

def verify() -> None:
    from core.foundation.self_test import run_self_tests
    if not run_self_tests():
        raise RuntimeError("Isolated security checks failed. Live policies were not changed.")
    corpus = Corpus()
    if not passkey_exists():
        create_passkey()
    binding = activation_binding()
    proof = require_passkey(operation="foundation.upgrade",payload=binding)
    result = activate_foundation(proof,binding)
    coverage = corpus.coverage()
    print_json({**result,"scripture_books":len(coverage["books"]),"new_testament_books":coverage["new_testament_books"],"translations":coverage["translations"]})
    print("MODULE 1 VERIFIED: protected rules, owner authentication, moral code and offline Scripture are ready.")
    print("Live voice matching and Windows audio hardware require their existing enrollment/runtime.")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ZÆNIA Module 1: rules, authentication and moral code")
    sub = parser.add_subparsers(dest="command",required=True)
    for name in ("verify","setup","rules","moral-code","foundation-status","list-mics","setup-voice-phrase","voice-auth","reset-voice-phrase","reset-approved-mic"):
        sub.add_parser(name)
    p=sub.add_parser("add-soft-rule")
    p.add_argument("--name","-n",required=True)
    p.add_argument("--description","-d",required=True)
    p.add_argument("--action","-a",choices=["allow","deny","require_reauth","log_only"],default="log_only")
    p.add_argument("--operation",action="append",required=True,help="Exact scope; repeat for several operations, or use '*' intentionally")
    p=sub.add_parser("check"); p.add_argument("operation")
    for name in ("delete","disable"):
        p=sub.add_parser(name); p.add_argument("rule_id")
    p=sub.add_parser("moral-notes"); p.add_argument("--file",type=Path,required=True)
    p=sub.add_parser("moral-check"); p.add_argument("--file",type=Path,required=True)
    p=sub.add_parser("scripture"); p.add_argument("reference")
    p=sub.add_parser("scripture-search"); p.add_argument("text");p.add_argument("--limit",type=int,default=20)
    p=sub.add_parser("scripture-context");p.add_argument("--file",type=Path,required=True)
    for name in ("backup","restore"):
        p=sub.add_parser(name);p.add_argument("file",type=Path)
    p=sub.add_parser("set-mic");p.add_argument("device_index",type=int)
    p=sub.add_parser("view-audit");p.add_argument("--lines","-n",type=int,default=25)
    p=sub.add_parser("audit-note");p.add_argument("message")
    p=sub.add_parser("api-token");p.add_argument("action",choices=["create","rotate","revoke","status"])
    return parser

def _run(args) -> None:
    command=args.command
    if command in ("verify","setup"):
        verify()
    elif command=="rules":
        print_json(list_rules(owner_read("rules.read")))
    elif command=="add-soft-rule":
        rule=create_rule(args.name,args.description,"soft",args.action,operations=tuple(args.operation))
        proof=require_passkey(operation="rules.add",payload=rule.to_dict())
        add_rule(rule,proof)
        print("Scoped soft rule added: "+rule.id)
    elif command=="check":
        proof=require_passkey(operation="rules.check",payload={"operation":args.operation})
        print_json(evaluate_operation(args.operation,proof))
    elif command in ("delete","disable"):
        proof=require_passkey(operation="rules."+command,payload={"rule_id":args.rule_id})
        print_json((delete_rule if command=="delete" else disable_rule)(args.rule_id,proof))
    elif command=="moral-code":
        print_json(load_policy(owner_read("moral.read")))
    elif command=="moral-notes":
        notes=_json_file(args.file)
        proof=require_passkey(operation="moral.notes.update",payload={"notes_digest":payload_digest(notes)})
        update_notes(notes,proof)
        print("Owner notes updated; protected moral principles remain enforced.")
    elif command=="moral-check":
        require_passkey()
        from dataclasses import asdict
        case=MoralCase(**_json_file(args.file))
        print_json({**asdict(evaluate_moral_case(case,context_required=True)),"execution_authorized":False})
    elif command=="scripture":
        print_json(Corpus().passage(args.reference,passphrase=owner_read("scripture.read")))
    elif command=="scripture-search":
        owner_read("scripture.read")
        print_json(Corpus().search(args.text,limit=args.limit))
    elif command=="scripture-context":
        record=_json_file(args.file)
        proof=require_passkey(operation="scripture.context.update",payload={"record_digest":payload_digest(record)})
        update_context(record,proof)
        print("Documented Scripture context saved in the encrypted vault.")
    elif command in ("backup","restore"):
        binding=(backup_binding if command=="backup" else restore_binding)(args.file)
        proof=require_passkey(operation="security."+command,payload=binding)
        (export_policy_backup if command=="backup" else restore_policy_backup)(args.file,proof,binding)
        print("Encrypted policy "+command+" complete.")
    elif command=="api-token":
        from core.api.auth import create_api_token,rotate_api_token,revoke_api_token,api_token_exists
        if args.action=="status":
            require_passkey();print("API token: "+("configured" if api_token_exists() else "not configured"))
        elif args.action=="revoke":
            revoke_api_token();print("API credential revoked.")
        else:
            token=(create_api_token if args.action=="create" else rotate_api_token)()
            print("Shown once locally. Keep this client credential private:")
            print(token)
    elif command=="foundation-status":
        require_passkey()
        print_json({"owner_passkey":passkey_exists(),"secure_directory":str(SECURE_DIR),"corpus":Corpus().coverage(),"operations":list(OPERATIONS)})
    elif command=="view-audit":
        require_passkey()
        if not 1 <= args.lines <= 500: raise ValueError("Use 1 to 500 audit lines.")
        if AUDIT_FILE.exists():
            for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines()[-args.lines:]:
                # Older logs may contain raw messages; do not echo them.
                try: event=json.loads(line)
                except ValueError: print("[legacy event omitted]");continue
                print_json({k:event[k] for k in ("timestamp","event","operation","reason_code") if k in event})
    elif command=="audit-note":
        require_passkey();audit("owner.note",args.message);print("A digest of the note was recorded; its text was not stored.")
    else:
        from core.foundation.auth import voice_passkey as voice
        if command=="list-mics":
            require_passkey();print_json(voice.list_input_devices())
        elif command=="set-mic":
            print_json(voice.save_allowed_mic_by_index(args.device_index))
        elif command=="setup-voice-phrase":
            voice.create_voice_phrase()
        elif command=="voice-auth":
            require_passkey()
            voice.require_voice_phrase()
            print("Supplementary phrase matched. This does not prove speaker identity or grant tool authority.")
        elif command=="reset-voice-phrase":
            voice.reset_voice_phrase();print("Supplementary voice phrase reset.")
        elif command=="reset-approved-mic":
            voice.reset_approved_mic();print("Approved microphone configuration reset.")

def main() -> None:
    args=build_parser().parse_args()
    try:
        _run(args)
    except (PermissionError,RuntimeError,ValueError,OSError,InvalidToken,TypeError) as error:
        print("Foundation stopped safely: "+("Encrypted data could not be authenticated." if isinstance(error,InvalidToken) else str(error)))
        raise SystemExit(1)

# Compatibility for launchers that previously imported a Typer app callable.
app = main

if __name__=="__main__":
    main()
