#!/usr/bin/env python3
"""A local PyPI simple index that hides files uploaded after a cutoff.

SimFoundry's installers leave most PyPI requirements unpinned, so a fresh build resolves
packages released after the SimFoundry commit it builds. Serving PyPI as it was at that
commit reproduces the environment upstream tested. pip 25.2, which the envs pin, has no
upload-date option of its own.

Usage: pypi_cutoff_proxy.py <cutoff, e.g. 2026-08-27T00:00:00Z> [port]
Then:  PIP_INDEX_URL=http://127.0.0.1:<port>/simple/ pip install ...
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "https://pypi.org/simple/"
JSON_TYPE = "application/vnd.pypi.simple.v1+json"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


CUTOFF = parse_time(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
CACHE = {}
LOCK = threading.Lock()


def filtered_project(project):
    with LOCK:
        if project in CACHE:
            return CACHE[project]
    request = urllib.request.Request(UPSTREAM + project + "/", headers={"Accept": JSON_TYPE})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, None
    # A file with no upload-time can't be placed before or after the cutoff, so keep it.
    # pip chooses from "files" only, so "versions" is passed through unchanged.
    data["files"] = [
        f for f in data["files"] if "upload-time" not in f or parse_time(f["upload-time"]) <= CUTOFF
    ]
    result = (200, json.dumps(data).encode())
    with LOCK:
        CACHE[project] = result
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        if len(parts) != 2 or parts[0] != "simple":
            self.send_error(404)
            return
        status, body = filtered_project(parts[1])
        if status != 200:
            self.send_error(status)
            return
        self.send_response(200)
        self.send_header("Content-Type", JSON_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"PyPI cutoff proxy on 127.0.0.1:{PORT}, hiding uploads after {CUTOFF.isoformat()}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
