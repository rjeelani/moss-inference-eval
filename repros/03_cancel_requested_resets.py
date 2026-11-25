"""Repro 3: cancel_requested goes back to false after a task is cancelled.

Starts a small task, cancels it after 3 seconds, then waits for it to end.
Expected: cancel_requested stays true (the docs call it "whether a cancel was requested").
What I saw: true right after cancel, false once the task is cancelled.
Cost: about $0.01.
"""
import time

from common import get, post

task = post("/tasks", {
    "goal": "Browse example.com and describe every link, then follow each one.",
    "environment": {"type": "browser", "start_url": "https://example.com"},
    "model": "moss-fast",
    "limits": {"max_runtime_seconds": 120, "max_cost_usd": 0.25},
}).json()
print("created:", task["id"], task["status"])

time.sleep(3)
c = post(f"/tasks/{task['id']}/cancel", {}).json()
print("after cancel call: status =", c["status"], "| cancel_requested =", c["cancel_requested"])

start = time.time()
while True:
    t = get(f"/tasks/{task['id']}").json()
    if t["status"] in ("completed", "failed", "cancelled"):
        break
    time.sleep(2)
print(f"ended {round(time.time() - start)} s later: status =", t["status"], "| cancel_requested =", t["cancel_requested"])
print("cost_usd =", t["usage"]["cost_usd"], "| error =", t["error"])
