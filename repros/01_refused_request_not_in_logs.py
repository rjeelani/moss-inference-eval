"""Repro 1: a refused request returns a request id, but the portal can't find it.

Run it, then paste the printed id into Logs & Traces > "Look up a request ID".
Expected: the request shows up (the docs say every response has an id, refused ones included).
What I saw: "No request with that ID in the last 30 days."
Cost: free (the request is refused before any model runs).
"""
from common import post

r = post("/responses", {"model": "not-a-real-model", "input": "hi"})
print("status:", r.status_code)
print("error:", r.json()["error"]["message"][:80])
print("request id (header):", r.headers.get("X-Moss-Request-Id"))
print("request id (body):  ", r.json()["error"].get("request_id"))
