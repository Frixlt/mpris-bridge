#!/usr/bin/env python3
"""What the extension costs in memory and CPU: the same headless Firefox, 12 tabs (one playing audio, eleven
without media), once with an empty control extension and once with this one.

  python3 tests/e2e/memory.py [ext|base] [tabs]      prints one JSON line
Memory is PSS (proportional set size), which does not count pages shared between Firefox's processes twice.
"""
import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SITE = os.path.join(os.path.dirname(__file__), "site")
mode = sys.argv[1] if len(sys.argv) > 1 else "ext"
tabs = int(sys.argv[2]) if len(sys.argv) > 2 else 12
PORT = 8124


class Site(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def do_GET(self):
        if self.path.startswith("/log"):
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *a):
        pass


def pss(pid):
    try:
        for line in open("/proc/%d/smaps_rollup" % pid):
            if line.startswith("Pss:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def cpu(pid):
    try:
        f = open("/proc/%d/stat" % pid).read().rsplit(")", 1)[1].split()
        return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
    except OSError:
        return 0.0


def session(root):
    out = []
    sid = os.getsid(root)
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.getsid(int(p)) == sid:
                    cmd = open("/proc/%s/cmdline" % p).read().split("\0")
                    if "firefox" in cmd[0] or "mpris-bridge-host" in cmd[0]:
                        out.append((int(p), cmd))
            except OSError:
                pass
    return out


def kind(cmd):
    if "mpris-bridge-host" in cmd[0]:
        return "helper"
    line = " ".join(c for c in cmd if c)  # Firefox rewrites its argv, so the arguments may share one string
    if "-contentproc" not in line:
        return "parent"
    return line.split()[-1]  # the process type: tab, extension, gpu, rdd, socket, ...


tone = os.path.join(SITE, "tone.ogg")
if not os.path.exists(tone):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=300",
                    "-c:a", "libvorbis", "-q:a", "0", tone], check=True)
server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Site)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % PORT
urls = [base + "/b.html"] + [base + "/plain.html?n=%d" % i for i in range(tabs - 1)]
src = os.path.join(ROOT, "extension") if mode == "ext" else os.path.join(os.path.dirname(__file__), "baseline-ext")
args = ["npx", "--yes", "web-ext", "run", "--source-dir", src, "--firefox", os.environ.get("FIREFOX", "firefox"),
        "--arg=-headless", "--no-input", "--no-reload", "--no-config-discovery",
        "--pref", "media.autoplay.default=0", "--pref", "media.autoplay.blocking_policy=0"]
for u in urls:
    args += ["--start-url", u]
proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
try:
    time.sleep(50)
    procs = session(proc.pid)
    t0 = {pid: cpu(pid) for pid, _ in procs}
    time.sleep(30)
    rows = {}
    for pid, cmd in procs:
        k = kind(cmd)
        r = rows.setdefault(k, {"n": 0, "pss_kb": 0, "cpu_s": 0.0})
        r["n"] += 1
        r["pss_kb"] += pss(pid)
        r["cpu_s"] += cpu(pid) - t0.get(pid, 0.0)
    total = sum(r["pss_kb"] for r in rows.values())
    print(json.dumps({"mode": mode, "tabs": tabs, "total_pss_kb": total, "by_kind": rows}))
finally:
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
