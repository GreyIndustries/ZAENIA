"""What ZAE knows about Grey's PC: its parts, read from Windows, so she can answer and advise from the real specs.

Read once a day (and at start-up) with one PowerShell CIM query plus
nvidia-smi: CPU, RAM sticks, graphics cards and their displays, motherboard,
drives, Windows version. Nothing identifying (serial numbers, user names,
network details) is collected, and nothing leaves the PC. Cached in
data/ui/pc_specs.json. Live load (CPU, RAM, GPU use) comes from the status bar.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPECS_FILE = PROJECT_ROOT / "data" / "ui" / "pc_specs.json"
MAX_AGE = 24 * 3600
_LOCK = threading.Lock()

_QUERY = r"""
$ErrorActionPreference = 'SilentlyContinue'
$o = [ordered]@{}
$o.cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed
$o.ram = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber)
$o.gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate)
$o.board = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product
$o.bios = Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion,ReleaseDate
$o.disks = @(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size)
$o.volumes = @(Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter,FileSystemLabel,Size,SizeRemaining)
$o.os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber
$o | ConvertTo-Json -Depth 4 -Compress
"""


def _run_query() -> dict[str, Any]:
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _QUERY], capture_output=True,
                         text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    raw = json.loads(out.stdout or "{}")
    try:
        smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,power.limit", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        raw["nvidia"] = [dict(zip(("name", "vramMb", "driver", "powerLimitW"), [p.strip() for p in line.split(",")])) for line in smi.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        raw["nvidia"] = []
    return raw


def _list(value: Any) -> list[dict[str, Any]]:
    return [v for v in (value if isinstance(value, list) else [value] if value else []) if isinstance(v, dict)]


def _gb(n: Any) -> float:
    try:
        return round(float(n) / 1024 ** 3, 1)
    except (TypeError, ValueError):
        return 0.0


def tidy(raw: dict[str, Any]) -> dict[str, Any]:
    """Plain specs from the raw Windows answers."""
    cpu = (_list(raw.get("cpu")) or [{}])[0]
    sticks = _list(raw.get("ram"))
    nvidia = {g.get("name"): g for g in _list(raw.get("nvidia"))}
    gpus = []
    for card in _list(raw.get("gpus")):
        name = str(card.get("Name") or "").strip()
        smi = nvidia.get(name, {})
        vram = round(int(smi["vramMb"]) / 1024, 1) if str(smi.get("vramMb", "")).isdigit() else None
        gpus.append({"name": name, "vramGb": vram, "driver": smi.get("driver") or card.get("DriverVersion"),
                     "powerLimitW": smi.get("powerLimitW"), "integrated": bool(re.search(r"\bRadeon\(TM\) Graphics\b|\bUHD\b|\bIris\b", name)),
                     "display": (f"{card['CurrentHorizontalResolution']}x{card['CurrentVerticalResolution']} @ {card.get('CurrentRefreshRate')} Hz"
                                 if card.get("CurrentHorizontalResolution") else None)})
    board = (_list(raw.get("board")) or [{}])[0]
    os_info = (_list(raw.get("os")) or [{}])[0]
    speed = max((int(s.get("ConfiguredClockSpeed") or s.get("Speed") or 0) for s in sticks), default=0)
    return {
        "cpu": {"name": " ".join(str(cpu.get("Name") or "").split()), "cores": cpu.get("NumberOfCores"),
                "threads": cpu.get("NumberOfLogicalProcessors"), "maxGhz": round((cpu.get("MaxClockSpeed") or 0) / 1000, 1)},
        "ram": {"totalGb": round(sum(_gb(s.get("Capacity")) for s in sticks)), "sticks": len(sticks), "speedMts": speed,
                "kind": "DDR5" if speed >= 4400 else "DDR4" if speed >= 1600 else "",
                "model": " ".join(sorted({f"{s.get('Manufacturer', '')} {str(s.get('PartNumber') or '').strip()}".strip() for s in sticks}))},
        "gpus": gpus,
        "board": " ".join(f"{board.get('Manufacturer', '')} {board.get('Product', '')}".replace("COMPUTER INC.", "").split()),
        "bios": ((_list(raw.get("bios")) or [{}])[0]).get("SMBIOSBIOSVersion"),
        "drives": [{"name": str(d.get("FriendlyName") or "").strip(), "type": f"{d.get('BusType', '')} {d.get('MediaType', '')}".strip(),
                    "sizeGb": round(_gb(d.get("Size")))} for d in _list(raw.get("disks"))],
        "volumes": [{"letter": v.get("DriveLetter"), "label": v.get("FileSystemLabel") or "", "sizeGb": round(_gb(v.get("Size"))),
                     "freeGb": round(_gb(v.get("SizeRemaining")))} for v in _list(raw.get("volumes")) if v.get("Size")],
        "os": f"{os_info.get('Caption', '')} (build {os_info.get('BuildNumber', '')})".strip(),
    }


def specs(*, refresh: bool = False, query: Callable[[], dict[str, Any]] = _run_query, path: Path = SPECS_FILE) -> dict[str, Any]:
    with _LOCK:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if not refresh and time.time() - float(cached.get("at", 0)) < MAX_AGE:
                return cached
        except (OSError, ValueError):
            cached = None
        try:
            data = tidy(query())
        except Exception:
            if cached:
                return cached
            raise
        data["at"] = time.time()
        from core.foundation.security.io import atomic_write
        atomic_write(path, json.dumps(data, indent=1).encode("utf-8"))
        return data


def summary(data: dict[str, Any]) -> str:
    """The specs as short plain lines for her brain."""
    cpu, ram = data.get("cpu", {}), data.get("ram", {})
    lines = [f"CPU: {cpu.get('name')} ({cpu.get('cores')} cores, {cpu.get('threads')} threads, up to {cpu.get('maxGhz')} GHz)."]
    lines.append(f"RAM: {ram.get('totalGb')} GB {ram.get('kind')} at {ram.get('speedMts')} MT/s ({ram.get('sticks')} sticks: {ram.get('model')}).")
    for gpu in data.get("gpus", []):
        bits = [gpu["name"]]
        if gpu.get("vramGb"):
            bits.append(f"{gpu['vramGb']:g} GB VRAM")
        if gpu.get("integrated"):
            bits.append("integrated in the CPU")
        if gpu.get("driver"):
            bits.append(f"driver {gpu['driver']}")
        if gpu.get("display"):
            bits.append(f"drives a {gpu['display']} display")
        lines.append("Graphics: " + ", ".join(bits) + ".")
    if data.get("board"):
        lines.append(f"Motherboard: {data['board']}" + (f" (BIOS {data['bios']})." if data.get("bios") else "."))
    for drive in data.get("drives", []):
        lines.append(f"Drive: {drive['name']}, {drive['type']}, {drive['sizeGb']} GB.")
    volumes = "; ".join(f"{v['letter']}: {v['freeGb']} of {v['sizeGb']} GB free" for v in data.get("volumes", []))
    if volumes:
        lines.append(f"Space: {volumes}.")
    if data.get("os"):
        lines.append(f"Windows: {data['os']}.")
    return "\n".join(lines)


_TOPIC = re.compile(r"\b(pc|computer|rig|specs?|hardware|cpu|processor|gpu|graphics|video card|vram|ram|ddr\d?|"
                    r"motherboard|bios|ssd|nvme|storage|hard drive|disk space|upgrade|fps|frame ?rate|can it run|drivers?|"
                    r"monitors?|resolution|refresh rate|overclock\w*|temps?|temperature|bottleneck|ryzen|nvidia|amd|rtx|radeon)\b", re.I)


def pc_context(question: str) -> str | None:
    """Specs for her brain when the question is about the PC or what it can run; None otherwise (saves context)."""
    if not _TOPIC.search(str(question or "")):
        return None
    try:
        data = specs()
    except Exception:
        return None
    text = "GREY'S PC (read from Windows on this PC; use these exact specs):\n" + summary(data)
    try:
        from core.api.status_bar import status_bar
        bar = status_bar()
        gpu = bar.get("gpu") or {}
        text += (f"\nRight now: CPU {bar.get('cpu')}% busy, RAM {bar.get('ramUsedGb')}/{bar.get('ramTotalGb')} GB used"
                 + (f", GPU {gpu.get('use')}% busy, {gpu.get('memoryUsedGb')}/{gpu.get('memoryTotalGb')} GB VRAM used, {gpu.get('temperature')} °C" if gpu else "") + ".")
    except Exception:
        pass
    return text


def warm() -> None:
    """Read the specs in the background at start-up so the first question doesn't wait."""
    threading.Thread(target=lambda: specs(), name="zaenia-pc-specs", daemon=True).start()
