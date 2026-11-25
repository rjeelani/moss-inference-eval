"""Small helper shared by the repro scripts. Reads MOSS_PROJECT_ID and MOSS_PROJECT_KEY
from the environment or from the .env file at the repo root."""
import os
from pathlib import Path

import requests

BASE = "https://inference.moss.dev/v1"

env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

HEADERS = {
    "Authorization": f"Bearer {os.environ['MOSS_PROJECT_ID']}:{os.environ['MOSS_PROJECT_KEY']}",
    "Content-Type": "application/json",
}


def post(path, body, extra_headers=None):
    return requests.post(BASE + path, json=body, headers={**HEADERS, **(extra_headers or {})}, timeout=60)


def get(path):
    return requests.get(BASE + path, headers=HEADERS, timeout=60)
