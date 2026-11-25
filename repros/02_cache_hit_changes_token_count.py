"""Repro 2: a reply cache hit returns the same text but a different output token count.

Sends the same request twice. The second one is a cache hit (documented, free, 0 input tokens).
Expected: same text, same output token count.
What I saw: same text, but output_tokens changes (for example 30 on the miss, 39 on the hit).
Cost: under $0.001.
"""
import time
import uuid

from common import post

body = {
    "model": "moss/fastlane-1",
    "instructions": "Answer in one short sentence.",
    "input": f"[{uuid.uuid4().hex[:6]}] What is a semantic index?",
    "max_output_tokens": 64,
}


def text(resp):
    return "".join(c.get("text", "") for o in resp["output"] for c in o.get("content", []))


replies = []
for name in ["first call", "second call"]:
    t = time.perf_counter()
    r = post("/responses", body).json()
    ms = round((time.perf_counter() - t) * 1000)
    replies.append(r)
    u = r["usage"]
    print(f"{name}: {ms} ms, input_tokens={u['input_tokens']}, output_tokens={u['output_tokens']}")

print("same text:", text(replies[0]) == text(replies[1]))
print("text:", text(replies[0]))
