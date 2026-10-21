"""Private source rollback snapshots with hash checks and local owner restore."""
from pathlib import Path
import hashlib
import json
import shutil
import uuid

from core.assistant_platform.store import ROOT, now_text
from core.foundation.security.io import atomic_write, reject_link, protect_storage


def allowed_source(relative):
    path=Path(relative)
    if path.is_absolute() or ".." in path.parts or any("backup" in part.casefold() or part.startswith(".") or part in {"target","node_modules","__pycache__","data"} for part in path.parts): return False
    normalized=path.as_posix()
    return (normalized.startswith(("core/","desktop/src/","desktop/src-tauri/src/","scripts/")) and path.suffix in {".py",".ts",".tsx",".css",".rs",".yaml",".yml",".ps1",".sh"}) or normalized in {"requirements.txt","requirements-module1.txt","requirements-operator.txt","desktop/package.json","desktop/package-lock.json","desktop/src-tauri/Cargo.toml","desktop/src-tauri/Cargo.lock","desktop/src-tauri/tauri.conf.json"}


def capture_release(store, *, root=ROOT):
    identifier=uuid.uuid4().hex
    destination=store.path.parent/"releases"/identifier
    protect_storage(destination)
    files,total=[],0
    candidates=[]
    for parent in ("core","desktop/src","desktop/src-tauri/src","scripts"):
        location=root/parent
        if location.exists():
            import os
            for current,dirs,names in os.walk(location,followlinks=False):
                dirs[:]=[name for name in dirs if not name.startswith(".") and "backup" not in name.casefold() and name!="__pycache__"]
                candidates += [Path(current)/name for name in names]
    candidates += [root/name for name in ("requirements.txt","requirements-module1.txt","requirements-operator.txt","desktop/package.json","desktop/package-lock.json","desktop/src-tauri/Cargo.toml","desktop/src-tauri/Cargo.lock","desktop/src-tauri/tauri.conf.json")]
    for source in candidates:
        relative=source.relative_to(root).as_posix()
        if not allowed_source(relative) or not source.is_file(): continue
        reject_link(source)
        data=source.read_bytes(); total+=len(data)
        if total>40*1024*1024 or len(files)>5000: raise ValueError("Source snapshot exceeds its bounded size.")
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        atomic_write(target,data,overwrite=False)
        files.append({"path":relative,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
    manifest={"id":identifier,"createdAt":now_text(),"files":files,"bytes":total}
    raw=json.dumps(manifest,sort_keys=True).encode()
    atomic_write(destination/"manifest.json",raw,overwrite=False)
    return store.put("release",{"files":len(files),"bytes":total,"sha256":hashlib.sha256(raw).hexdigest(),"status":"snapshot_ready"},identifier)


def validate_release(store, identifier):
    record=store.get("release",identifier)
    if not record: raise ValueError("Unknown source snapshot.")
    folder=store.path.parent/"releases"/identifier
    reject_link(folder)
    raw=(folder/"manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record["sha256"]: raise ValueError("Snapshot manifest changed.")
    manifest=json.loads(raw)
    if not isinstance(manifest.get("files"),list) or len(manifest["files"])>5000: raise ValueError("Invalid snapshot manifest.")
    for entry in manifest["files"]:
        if not allowed_source(entry["path"]): raise ValueError("Snapshot contains an out-of-scope path.")
        source=folder/entry["path"]; reject_link(source)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=entry["sha256"]: raise ValueError("Snapshot file changed.")
    return manifest


def restore_release(store, identifier, *, root=ROOT):
    manifest=validate_release(store,identifier)
    # Check every destination before the first replacement.
    for entry in manifest["files"]:
        target=root/entry["path"]; reject_link(target)
        target.resolve().relative_to(root.resolve())
    recovery=capture_release(store,root=root)
    for entry in manifest["files"]:
        target=root/entry["path"]
        atomic_write(target,(store.path.parent/"releases"/identifier/entry["path"]).read_bytes())
    return {"restoredFiles":len(manifest["files"]),"recoverySnapshot":recovery["id"],"restartRequired":True}


def main():
    import argparse
    from core.assistant_platform.store import PlatformStore
    from core.foundation.auth.passkey import require_passkey,consume_fresh_auth
    from core.foundation.rules.policy import assert_owner_scope
    parser=argparse.ArgumentParser(description="Owner-authenticated source rollback. Close the app/API before restoring.")
    parser.add_argument("snapshot")
    args=parser.parse_args(); store=PlatformStore()
    import requests
    try:
        running=requests.get("http://127.0.0.1:8766/health",timeout=2)
        if running.status_code==200 and running.json().get("service")=="zaenia_api":
            raise ValueError("Stop the local ZAE API before restoring source files, then run this rollback again.")
    except requests.RequestException:
        pass
    manifest=validate_release(store,args.snapshot)
    binding={"snapshot":args.snapshot,"manifest":store.get("release",args.snapshot)["sha256"]}
    proof=require_passkey(operation="profile.restore",payload=binding)
    assert_owner_scope(proof,"profile.restore"); consume_fresh_auth(proof,operation="profile.restore",payload=binding)
    print(f"Restore {len(manifest['files'])} source/configuration files. Data, credentials, models and executables are excluded.")
    print("Close ZAE's app and stop the API before continuing. Restart/rebuild after this operation.")
    if input("Type REVIEW "+args.snapshot[:8]+": ").strip()!="REVIEW "+args.snapshot[:8]: return
    if input("Type RESTORE "+args.snapshot[:8]+": ").strip()!="RESTORE "+args.snapshot[:8]: return
    print(restore_release(store,args.snapshot))


if __name__=="__main__": main()
