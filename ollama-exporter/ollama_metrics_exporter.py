#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import json
import subprocess
import sys

PORT = 8000
OLLAMA_URL = "http://localhost:11434"


class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        ollama_up = 0
        models_total = 0
        gpu_util = 0.0
        gpu_mem_bytes = 0.0

        # Stato Ollama + modelli
        try:
            with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=1) as resp:
                if resp.status == 200:
                    ollama_up = 1
                    data = json.load(resp)
                    models = data.get("models", [])
                    models_total = len(models)
        except Exception:
            pass

        # GPU via nvidia-smi
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
            ).decode().strip().splitlines()[0]
            util_str, mem_str = [x.strip() for x in out.split(",")]
            gpu_util = float(util_str)
            gpu_mem_bytes = float(mem_str) * 1024 * 1024
        except Exception:
            pass

        body = f"""# HELP ollama_up Ollama HTTP health (1=up,0=down)
# TYPE ollama_up gauge
ollama_up {ollama_up}
# HELP ollama_models_total Number of models reported by /api/tags
# TYPE ollama_models_total gauge
ollama_models_total {models_total}
# HELP ollama_gpu_utilization_percent GPU utilization for Ollama node
# TYPE ollama_gpu_utilization_percent gauge
ollama_gpu_utilization_percent {gpu_util}
# HELP ollama_gpu_memory_used_bytes GPU memory used on Ollama node
# TYPE ollama_gpu_memory_used_bytes gauge
ollama_gpu_memory_used_bytes {gpu_mem_bytes}
"""

        body_bytes = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main():
    server = HTTPServer(("", PORT), MetricsHandler)
    print(f"Ollama metrics exporter listening on :{PORT}/metrics", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()

