"""Tiny HTTP client for Moss Inference + Tasks that logs every call to JSONL.

Credentials come from MOSS_PROJECT_ID / MOSS_PROJECT_KEY (never hard-coded,
never written to logs - the Authorization header is redacted).
"""
import json
import os
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("MOSS_INFERENCE_URL", "https://inference.moss.dev/v1")
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Load KEY=VALUE lines from a gitignored .env at the repo root (env vars win).
_env = LOG_DIR.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))


def creds():
    pid, key = os.environ.get("MOSS_PROJECT_ID"), os.environ.get("MOSS_PROJECT_KEY")
    if not pid or not key:
        raise SystemExit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY first (see README).")
    return pid, key


class Moss:
    def __init__(self, log_name, bad_key=False):
        pid, key = creds()
        self.token = "bad:bad" if bad_key else f"{pid}:{key}"
        self.log_path = LOG_DIR / f"{log_name}.jsonl"
        self.s = requests.Session()

    def call(self, method, path, body=None, headers=None, stream=False, label="", timeout=120):
        h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        h.update(headers or {})
        t0 = time.perf_counter()
        try:
            r = self.s.request(method, BASE_URL + path, json=body, headers=h,
                               stream=stream, timeout=timeout)
        except requests.RequestException as e:
            self._log(label, method, path, body, None, None, time.perf_counter() - t0, error=str(e))
            raise
        elapsed = time.perf_counter() - t0  # time to response headers when streaming
        if stream:
            return r, t0
        try:
            data = r.json()
        except ValueError:
            data = r.text[:2000]
        self._log(label, method, path, body, r.status_code, dict(r.headers), elapsed, data)
        return r.status_code, data, dict(r.headers), elapsed

    def _log(self, label, method, path, body, status, headers, elapsed, data=None, error=None):
        rec = {"ts": time.time(), "label": label, "method": method, "path": path,
               "request": body, "status": status, "elapsed_s": round(elapsed, 4),
               "response_headers": {k: v for k, v in (headers or {}).items()
                                    if k.lower().startswith(("x-", "retry", "content-type"))},
               "response": data, "error": error}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")


def save_result(name, obj):
    p = LOG_DIR.parent / "results" / f"{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    print(f"\n[saved] {p}")
