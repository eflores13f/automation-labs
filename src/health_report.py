# This is a system health report
# Work in progress


from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HealthSnapshot:
    timestamp: str
    hostname: str
    user: str
    os: str
    kernel: str
    uptime: str
    load_avg: str
    cpu_cores: int
    mem_total_gb: float
    mem_used_gb: float
    mem_used_pct: float
    disk_total_gb: float
    disk_used_gb: float
    disk_used_pct: float
    top_processes: list[str]


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except Exception:
        return ""


def _uptime_pretty() -> str:
    # Linux: /proc/uptime -> seconds
    try:
        seconds = float(Path("/proc/uptime").read_text().split()[0])
        minutes, _ = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return _run(["uptime", "-p"]) or "unknown"


def _load_avg() -> str:
    try:
        one, five, fifteen = os.getloadavg()
        return f"{one:.2f} {five:.2f} {fifteen:.2f}"
    except Exception:
        return "n/a"


def _memory_gb() -> tuple[float, float, float]:
    # Linux: /proc/meminfo (kB)
    meminfo = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, val = line.split(":", 1)
            meminfo[key.strip()] = val.strip()
        total_kb = float(meminfo["MemTotal"].split()[0])
        avail_kb = float(meminfo["MemAvailable"].split()[0])
        used_kb = total_kb - avail_kb
        total_gb = total_kb / 1024 / 1024
        used_gb = used_kb / 1024 / 1024
        used_pct = (used_kb / total_kb) * 100 if total_kb else 0.0
        return total_gb, used_gb, used_pct
    except Exception:
        return 0.0, 0.0, 0.0


def _disk_gb(path: str = "/") -> tuple[float, float, float]:
    usage = shutil.disk_usage(path)
    total_gb = usage.total / 1024 / 1024 / 1024
    used_gb = (usage.total - usage.free) / 1024 / 1024 / 1024
    used_pct = (used_gb / total_gb) * 100 if total_gb else 0.0
    return total_gb, used_gb, used_pct


def _top_processes(n: int = 8) -> list[str]:
    # Prefer ps (standard on Ubuntu)
    out = _run(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"])
    if not out:
        return []
    lines = out.splitlines()
    # Skip header; take top N
    top = lines[1 : 1 + n]
    return [line.strip() for line in top]


def take_snapshot() -> HealthSnapshot:
    now = dt.datetime.now().isoformat(timespec="seconds")
    hostname = socket.gethostname()
    user = os.getenv("USER", "unknown")
    os_name = platform.system()
    kernel = platform.release()
    cpu_cores = os.cpu_count() or 0

    mem_total_gb, mem_used_gb, mem_used_pct = _memory_gb()
    disk_total_gb, disk_used_gb, disk_used_pct = _disk_gb("/")

    return HealthSnapshot(
        timestamp=now,
        hostname=hostname,
        user=user,
        os=os_name,
        kernel=kernel,
        uptime=_uptime_pretty(),
        load_avg=_load_avg(),
        cpu_cores=cpu_cores,
        mem_total_gb=mem_total_gb,
        mem_used_gb=mem_used_gb,
        mem_used_pct=mem_used_pct,
        disk_total_gb=disk_total_gb,
        disk_used_gb=disk_used_gb,
        disk_used_pct=disk_used_pct,
        top_processes=_top_processes(),
    )


def render_text(s: HealthSnapshot) -> str:
    lines = []
    lines.append("=== System Health Report ===")

    status = health_status(s.mem_used_pct, s.disk_used_pct, s.load_avg)
    lines.append(f"Overall Status: {status}")
    lines.append("")

    lines.append(f"Time:     {s.timestamp}")
    lines.append(f"Host:     {s.hostname}")
    lines.append(f"User:     {s.user}")
    lines.append(f"OS:       {s.os} ({s.kernel})")
    lines.append(f"Uptime:   {s.uptime}")
    lines.append(f"LoadAvg:  {s.load_avg}   (1m 5m 15m)")
    lines.append(f"CPU:      {s.cpu_cores} cores")
    lines.append("")
    lines.append("Memory:")
    lines.append(f"  Used:   {s.mem_used_gb:.2f} GB / {s.mem_total_gb:.2f} GB  ({s.mem_used_pct:.1f}%)")
    lines.append("")
    lines.append("Disk (/):")
    lines.append(f"  Used:   {s.disk_used_gb:.2f} GB / {s.disk_total_gb:.2f} GB  ({s.disk_used_pct:.1f}%)")
    lines.append("")
    lines.append("Top CPU processes (pid command %cpu %mem):")
    if s.top_processes:
        lines.extend([f"  {p}" for p in s.top_processes])
    else:
        lines.append("  (unable to read process list)")
    lines.append("")
    return "\n".join(lines)

def health_status(mem_pct: float, disk_pct: float, load_avg: str) -> str:
    one_min = float(load_avg.split()[0]) if load_avg != "n/a" else 0

    if mem_pct > 85 or disk_pct > 90 or one_min > os.cpu_count():
        return "CRITICAL"

    if mem_pct > 70 or disk_pct > 75:
        return "WARNING"

    return "OK"


def save_report(text: str, out_dir: Path = Path("reports")) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"health-{stamp}.txt"
    path.write_text(text)
    return path

