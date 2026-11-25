"""Repro 4: max_runtime_seconds 60.5 is accepted and saved as 60.

Expected: a 400 error, like the one you get for "60" as a string.
What I saw: 202 accepted, and the task shows max_runtime_seconds 60.
The task is cancelled right away. Cost: close to $0.
"""
from common import post

base = {
    "goal": "Report the page title.",
    "environment": {"type": "browser", "start_url": "https://example.com"},
    "model": "moss-fast",
}

r = post("/tasks", {**base, "limits": {"max_runtime_seconds": "60", "max_cost_usd": 0.05}})
print('"60" as a string ->', r.status_code, r.json().get("error", {}).get("message"))

r = post("/tasks", {**base, "limits": {"max_runtime_seconds": 60.5, "max_cost_usd": 0.05}})
t = r.json()
print("60.5 as a number ->", r.status_code, "| saved limits:", t.get("limits"))
if r.status_code == 202:
    post(f"/tasks/{t['id']}/cancel", {})
    print("cancelled", t["id"])
