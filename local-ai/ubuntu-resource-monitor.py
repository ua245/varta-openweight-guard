"""Small read-only Ubuntu resource sampler, bound to localhost."""
import json
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE = {"available": False}
LOCK = threading.Lock()


def cpu_times():
    result = {}
    for line in Path("/proc/stat").read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith("cpu"):
            values = list(map(int, fields[1:9]))
            result[fields[0]] = (sum(values), values[3] + values[4], values[4])
    return result


def network():
    interface = "eth0"
    for line in Path("/proc/net/route").read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) > 2 and fields[1] == "00000000":
            interface = fields[0]
            break
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, values = line.split(":", 1)
        if name.strip() == interface:
            fields = values.split()
            return interface, int(fields[0]), int(fields[8])
    return interface, 0, 0


def sample_loop():
    global STATE
    previous_cpu = cpu_times()
    previous_net = network()
    previous_time = time.monotonic()
    while True:
        time.sleep(1)
        try:
            now = time.monotonic()
            current_cpu, current_net = cpu_times(), network()
            usage, io_wait = {}, 0.0
            for key, (total, idle, wait) in current_cpu.items():
                old = previous_cpu.get(key, (total, idle, wait))
                delta = total - old[0]
                usage[key] = round(max(0, min(100, 100 * (delta - (idle - old[1])) / delta)), 1) if delta else 0
                if key == "cpu" and delta:
                    io_wait = round(100 * (wait - old[2]) / delta, 1)
            memory = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                memory[key] = int(value.split()[0]) * 1024
            disk = shutil.disk_usage("/")
            elapsed = max(0.001, now - previous_time)
            state = {
                "available": True,
                "updated": time.time(),
                "uptime_seconds": float(Path("/proc/uptime").read_text().split()[0]),
                "cpu_percent": usage.pop("cpu", 0),
                "cpu_cores": list(usage.values()),
                "cpu_iowait_percent": io_wait,
                "load_average": list(map(float, Path("/proc/loadavg").read_text().split()[:3])),
                "memory": {"total": memory["MemTotal"], "used": memory["MemTotal"] - memory["MemAvailable"], "available": memory["MemAvailable"]},
                "disk": {"mount": "/", "total": disk.total, "used": disk.used, "free": disk.free},
                "network": {"interface": current_net[0], "rx_bytes_per_second": max(0, (current_net[1] - previous_net[1]) / elapsed), "tx_bytes_per_second": max(0, (current_net[2] - previous_net[2]) / elapsed)},
                "gpu": {"name": "Apple M5 Pro · virtual Vulkan", "available": Path("/dev/dri/renderD128").exists(), "utilization_percent": None},
            }
            with LOCK:
                STATE = state
            previous_cpu, previous_net, previous_time = current_cpu, current_net, now
        except (OSError, ValueError, KeyError) as exc:
            with LOCK:
                STATE = {"available": False, "updated": time.time(), "error": type(exc).__name__}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/resources":
            self.send_error(404)
            return
        with LOCK:
            body = json.dumps(STATE).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin")
        if origin in ("http://127.0.0.1:8765", "http://localhost:8765"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=sample_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", 9109), Handler).serve_forever()
