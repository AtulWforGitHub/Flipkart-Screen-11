from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


REMOTE_HELPER = r'''
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MODE = sys.argv[1]
SERVICE = sys.argv[2]
ACTIVITY_LOG = Path(sys.argv[3])


def parse_cycle_markers():
    markers = []
    if not ACTIVITY_LOG.exists():
        return markers
    for line in ACTIVITY_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "Cycle #" not in line:
            continue
        ts = line.split(" - ", 1)[0].strip()[:19]
        markers.append({"timestamp": ts, "line": line})
    return markers


def latest_app_start(service: str):
    proc = subprocess.run(
        ["journalctl", "-u", service, "--no-pager", "-o", "short-iso"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    latest = None
    for line in proc.stdout.splitlines():
        if "Application started" in line:
            latest = line[:19].replace("T", " ")
    return latest


def capture_window(service: str, start_ts: str, end_ts: str, output_path: str):
    journal = subprocess.run(
        ["journalctl", "-u", service, "--since", start_ts, "--until", end_ts, "--no-pager"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
    )
    pattern = re.compile(r"INFO - (200 [A-Z0-9]+|  [1-9]\.|  → NEP adjusted)")
    lines = [line for line in journal.stdout.splitlines() if pattern.search(line)]
    Path(output_path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return lines


if MODE == "state":
    markers = parse_cycle_markers()
    print(json.dumps({
        "latest_cycle": markers[-1]["timestamp"] if markers else None,
        "previous_cycle": markers[-2]["timestamp"] if len(markers) >= 2 else None,
        "latest_app_start": latest_app_start(SERVICE),
    }))
elif MODE == "capture-latest":
    output_path = sys.argv[4]
    state_markers = parse_cycle_markers()
    if not state_markers:
        raise SystemExit("No cycle markers found")
    end_ts = state_markers[-1]["timestamp"]
    app_start = latest_app_start(SERVICE)
    if app_start and app_start < end_ts:
        start_ts = app_start
    elif len(state_markers) >= 2:
        start_ts = state_markers[-2]["timestamp"]
    else:
        raise SystemExit("Need at least one app start or two cycle markers")
    lines = capture_window(SERVICE, start_ts, end_ts, output_path)
    print(json.dumps({"start": start_ts, "end": end_ts, "line_count": len(lines), "output": output_path}))
elif MODE == "wait-next":
    after_ts = sys.argv[4]
    output_path = sys.argv[5]
    sleep_seconds = int(sys.argv[6])
    while True:
        markers = parse_cycle_markers()
        target = next((marker for marker in markers if marker["timestamp"] > after_ts), None)
        if target is not None:
            lines = capture_window(SERVICE, after_ts, target["timestamp"], output_path)
            print(json.dumps({"start": after_ts, "end": target["timestamp"], "line_count": len(lines), "output": output_path}))
            break
        time.sleep(sleep_seconds)
else:
    raise SystemExit(f"Unknown mode: {MODE}")
'''


def run_ssh_python(server: str, args: list[str]) -> str:
    cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=20",
        server,
        "python3",
        "-",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        input=REMOTE_HELPER,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or f"ssh python helper exited with {proc.returncode}"
        raise RuntimeError(message)
    return proc.stdout.strip()


def scp_download(server: str, remote_path: str, local_path: Path) -> None:
    cmd = ["scp", f"{server}:{remote_path}", str(local_path)]
    subprocess.run(cmd, check=True)


def run_compare(before: Path, after: Path, limit: int) -> int:
    cmd = [sys.executable, "compare_cycle_offer_logs.py", str(before), str(after), "--limit", str(limit)]
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and compare Hostinger Flipkart cycles.")
    parser.add_argument("mode", choices=["state", "capture-latest", "wait-next", "compare"])
    parser.add_argument("--server", default="root@187.127.191.228")
    parser.add_argument("--service", default="flipkart")
    parser.add_argument("--activity-log", default="/root/flipkart-app/activity.log")
    parser.add_argument("--remote-output", default="/root/flipkart-app/captured_cycle.log")
    parser.add_argument("--local-output", default="captured_cycle.log")
    parser.add_argument("--after-ts")
    parser.add_argument("--sleep-seconds", type=int, default=30)
    parser.add_argument("--before-log")
    parser.add_argument("--after-log")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.mode == "state":
        print(run_ssh_python(args.server, ["state", args.service, args.activity_log]))
        return 0

    if args.mode == "capture-latest":
        output = run_ssh_python(args.server, ["capture-latest", args.service, args.activity_log, args.remote_output])
        print(output)
        scp_download(args.server, args.remote_output, Path(args.local_output))
        return 0

    if args.mode == "wait-next":
        if not args.after_ts:
            raise SystemExit("--after-ts is required for wait-next")
        output = run_ssh_python(
            args.server,
            ["wait-next", args.service, args.activity_log, args.after_ts, args.remote_output, str(args.sleep_seconds)],
        )
        print(output)
        scp_download(args.server, args.remote_output, Path(args.local_output))
        return 0

    if not args.before_log or not args.after_log:
        raise SystemExit("--before-log and --after-log are required for compare")
    return run_compare(Path(args.before_log), Path(args.after_log), args.limit)


if __name__ == "__main__":
    raise SystemExit(main())