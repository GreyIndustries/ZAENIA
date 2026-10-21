"""Bounded background jobs with real stages, explicit priority and cancellation."""
from __future__ import annotations

from collections import deque
import threading
import time
import uuid
import os

from core.assistant_platform.performance import WorkCancelled, work_context
from core.assistant_platform.store import text, now_text


class JobContext:
    def __init__(self, manager, identifier, cancel):
        self.manager, self.id, self.cancel = manager, identifier, cancel
        self.last_check = 0.

    def check(self, *, force=False):
        if self.manager.store is not None and (force or time.monotonic()-self.last_check>.25):
            saved = self.manager.store.get("job",self.id)
            if saved and saved.get("cancelRequested"): self.cancel.set()
            self.last_check = time.monotonic()
        if self.cancel.is_set():
            raise WorkCancelled("Cancelled by owner.")

    def progress(self, stage, *, done=None, total=None, detail=""):
        self.check()
        with self.manager.lock:
            self.manager.jobs[self.id].update(stage=stage, completedUnits=done, totalUnits=total,
                                               detail=str(detail)[:600], updatedAt=now_text())
            self.manager.save(self.id)


class JobManager:
    def __init__(self, *, workers=2):
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.jobs, self.callbacks, self.cancels = {}, {}, {}
        self.settled = {}
        self.queue = deque()
        self.workers = workers
        self.started = False
        self.store = None

    def attach(self, store):
        with self.lock:
            if self.store is not None: return
            self.store = store
            for row in store.list("job"):
                if row.get("status") in {"queued", "running"} and not process_alive(row.get("ownerPid")):
                    row.update(status="interrupted", stage="Interrupted by restart", detail="Review the previous request before starting it again.")
                    store.put("job", row, row["id"])

    def save(self, identifier):
        if self.store is not None:
            public = self.snapshot(identifier)
            old = self.store.get("job",identifier)
            if old: self.store.patch("job",identifier,public,preserve_true=("cancelRequested",))
            else: self.store.put("job",public,identifier)

    def submit(self, title, callback, *, priority=False, automatic=False):
        title = text(title, "Job title", 200)
        with self.condition:
            if sum(row["status"] in {"queued", "running"} for row in self.jobs.values()) >= 12:
                raise ValueError("Twelve jobs are already queued or running.")
            # Bound completed job history without removing active work.
            for key in list(self.jobs):
                if len(self.jobs) < 100:
                    break
                if self.jobs[key]["status"] not in {"queued", "running"}:
                    self.jobs.pop(key); self.cancels.pop(key, None); self.settled.pop(key,None)
            identifier = uuid.uuid4().hex
            self.jobs[identifier] = {"id": identifier, "title": title, "priority": bool(priority),
                "automatic": bool(automatic), "ownerPid":os.getpid(), "status": "queued", "stage": "Queued", "detail": "",
                "completedUnits": None, "totalUnits": None, "createdAt": now_text(), "updatedAt": now_text(),
                "startedAt": None, "elapsedSeconds": 0, "result": None}
            self.callbacks[identifier] = callback
            self.cancels[identifier] = threading.Event()
            self.settled[identifier] = threading.Event()
            if priority: self.queue.appendleft(identifier)
            else: self.queue.append(identifier)
            if not self.started:
                self.started = True
                for index in range(self.workers):
                    threading.Thread(target=self._run, name=f"zae-job-{index}", daemon=True).start()
            self.condition.notify_all()
            self.save(identifier)
            return self.snapshot(identifier)

    def snapshot(self, identifier=None):
        with self.lock:
            rows = [self.jobs[identifier]] if identifier in self.jobs else [] if identifier else list(self.jobs.values())
            return self._public(rows, identifier)

    def _public(self, rows, identifier):
        result = []
        for row in rows:
            copy = {k: v for k, v in row.items() if k != "_started"}
            if row.get("_started") and row["status"] == "running":
                copy["elapsedSeconds"] = round(time.monotonic()-row["_started"], 1)
            result.append(copy)
        return (result[0] if result else None) if identifier else list(reversed(result))

    def cancel(self, identifier):
        with self.condition:
            if identifier not in self.jobs:
                if self.store is not None:
                    row = self.store.get("job",identifier)
                    if row and row["status"] in {"queued","running"}:
                        return self.store.patch("job",identifier,{"cancelRequested":True})
                raise ValueError("That job no longer exists.")
            if self.jobs[identifier]["status"] in {"queued", "running"}:
                self.cancels[identifier].set()
                self.jobs[identifier]["detail"] = "Cancellation requested; waiting for the current local step to yield."
                self.condition.notify_all()
            return self.snapshot(identifier)

    def foreground(self):
        with self.condition:
            for identifier, row in self.jobs.items():
                if row["automatic"] and not row["priority"] and row["status"] in {"queued", "running"}:
                    self.cancels[identifier].set()

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: bool(self.queue))
                identifier = self.queue.popleft()
                row = self.jobs[identifier]
                callback = self.callbacks.pop(identifier)
                row.update(status="running", stage="Starting", startedAt=now_text(), _started=time.monotonic())
                self.save(identifier)
            context = JobContext(self, identifier, self.cancels[identifier])
            try:
                with work_context("priority" if row["priority"] else "deferred", context.cancel):
                    context.check()
                    result = callback(context)
                    context.check(force=True)
                with self.lock:
                    row.update(status="completed", stage="Complete", result=result, detail="")
            except WorkCancelled:
                with self.lock: row.update(status="cancelled", stage="Cancelled", detail="Work stopped before the next step.")
            except Exception as error:
                with self.lock: row.update(status="failed", stage="Failed", detail=f"Local step failed ({type(error).__name__}). Review the source or retry explicitly.")
            finally:
                with self.lock: row.update(updatedAt=now_text(), elapsedSeconds=round(time.monotonic()-row["_started"],1))
                try: self.save(identifier)
                finally: self.settled[identifier].set()


JOBS = JobManager()


def process_alive(pid):
    if type(pid) is not int or pid<=0: return False
    if pid==os.getpid(): return True
    if os.name=="nt":
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle: return ctypes.get_last_error()==5
        try:
            code=wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid,0); return True
    except ProcessLookupError: return False
    except PermissionError: return True
