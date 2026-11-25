"""Probe the Moss Tasks API (async browser agent). Every task carries a small cost cap.

Usage:
  python harness/tasks_probe.py validation        # free: bad requests only
  python harness/tasks_probe.py happy             # one real task, polled to completion
  python harness/tasks_probe.py schema            # task with output_schema
  python harness/tasks_probe.py idempotency       # same Idempotency-Key twice
  python harness/tasks_probe.py cancel            # create then cancel
  python harness/tasks_probe.py limits            # tiny budget / tiny runtime -> budget_exceeded / time_limit
  python harness/tasks_probe.py queue             # try to exceed 20 queued tasks (cancels everything after)
  python harness/tasks_probe.py all               # everything except queue
"""
import sys
import time
import uuid

from client import Moss, save_result

TERMINAL = {"completed", "failed", "cancelled"}
ENV = {"type": "browser", "start_url": "https://example.com"}


def create(m, body, key=None, label="create"):
    h = {"Idempotency-Key": key} if key else None
    return m.call("POST", "/tasks", body, headers=h, label=label)


def poll(m, tid, every=5, max_wait=900):
    t0 = time.time()
    seen = []
    while time.time() - t0 < max_wait:
        st, d, _, _ = m.call("GET", f"/tasks/{tid}", label=f"poll-{tid[-6:]}")
        if st != 200:
            return st, d, seen
        if not seen or seen[-1][1] != d["status"]:
            seen.append((round(time.time() - t0, 1), d["status"]))
        if d["status"] in TERMINAL:
            return st, d, seen
        time.sleep(every)
    return 0, {"error": "poll timeout"}, seen


def summarize(d):
    if not isinstance(d, dict):
        return d
    return {k: d.get(k) for k in ("id", "status", "result", "verification", "usage", "error")}


def validation(m):
    cases = {
        "unknown_top_level_field": {"goal": "x", "environment": {"type": "browser"}, "bogus": 1},
        "missing_goal": {"environment": {"type": "browser"}},
        "missing_environment": {"goal": "x"},
        "bad_env_type": {"goal": "x", "environment": {"type": "desktop"}},
        "bad_start_url": {"goal": "x", "environment": {"type": "browser", "start_url": "ftp://x"}},
        "goal_too_long": {"goal": "a" * 20001, "environment": {"type": "browser"}},
        "cost_below_min": {"goal": "x", "environment": {"type": "browser"}, "limits": {"max_cost_usd": 0.001}},
        "cost_above_max": {"goal": "x", "environment": {"type": "browser"}, "limits": {"max_cost_usd": 51}},
        "runtime_below_min": {"goal": "x", "environment": {"type": "browser"}, "limits": {"max_runtime_seconds": 5}},
        "bad_effort": {"goal": "x", "environment": {"type": "browser"}, "effort": "extreme"},
        "bad_schema": {"goal": "x", "environment": {"type": "browser"}, "output_schema": {"type": "array"}},
        "unknown_model": {"goal": "x", "environment": {"type": "browser"}, "model": "nope"},
    }
    res = {}
    for name, body in cases.items():
        st, d, _, _ = create(m, body, label=f"val-{name}")
        res[name] = {"status": st, "body": d}
        print(f"{name:28} -> {st} {str(d)[:140]}")
        if st in (200, 201, 202) and isinstance(d, dict) and d.get("id"):  # accepted when it shouldn't be
            m.call("POST", f"/tasks/{d['id']}/cancel", label="val-cleanup")
    st, d, _, _ = m.call("GET", "/tasks/task_" + "0" * 32, label="val-notfound")
    res["get_nonexistent"] = {"status": st, "body": d}
    print("get_nonexistent ->", st, str(d)[:140])
    return res


def edges(m):
    """Type confusion, boundaries, nested unknown fields, size limits. Anything accepted is cancelled at once."""
    B = lambda **kw: {"goal": "Report the page title.", "environment": {"type": "browser", "start_url": "https://example.com"},
                      "model": "moss-fast", "limits": {"max_runtime_seconds": 60, "max_cost_usd": 0.05}, **kw}
    cases = {
        "goal_whitespace_only": B(goal="   \n\t  "),
        "goal_exactly_20000": B(goal="Report the page title. " + "x" * (20000 - 23)),
        "cost_as_string": B(limits={"max_runtime_seconds": 60, "max_cost_usd": "0.05"}),
        "cost_as_bool_true": B(limits={"max_runtime_seconds": 60, "max_cost_usd": True}),
        "runtime_float": B(limits={"max_runtime_seconds": 60.5, "max_cost_usd": 0.05}),
        "runtime_as_string": B(limits={"max_runtime_seconds": "60", "max_cost_usd": 0.05}),
        "unknown_field_in_limits": B(limits={"max_runtime_seconds": 60, "max_cost_usd": 0.05, "max_steps": 3}),
        "unknown_field_in_environment": B(environment={"type": "browser", "start_url": "https://example.com", "viewport": "1x1"}),
        "start_url_bare_host": B(environment={"type": "browser", "start_url": "example.com"}),
        "start_url_javascript": B(environment={"type": "browser", "start_url": "javascript:void(0)"}),
        "metadata_string": B(metadata="hello"),
        "metadata_4001_bytes": B(metadata={"k": "x" * 3995}),
        "schema_over_20000_bytes": B(output_schema={"type": "object", "description": "x" * 20100}),
        "schema_invalid_jsonschema": B(output_schema={"type": "object", "properties": {"a": {"type": "not-a-type"}}}),
        "effort_uppercase": B(effort="LOW"),
        "model_undocumented_fast_beta": B(model="moss-fast-beta"),
        "body_over_256KiB": B(metadata={"k": "x" * 300000}),
    }
    res = {}
    for name, body in cases.items():
        st, d, _, _ = create(m, body, label=f"edge-{name}")
        accepted = st in (200, 201, 202) and isinstance(d, dict) and d.get("id")
        if accepted:
            m.call("POST", f"/tasks/{d['id']}/cancel", label="edge-cleanup")
        msg = d.get("error", {}).get("message") if isinstance(d, dict) and d.get("error") else None
        res[name] = {"status": st, "accepted": bool(accepted), "message": msg,
                     "echo_limits": d.get("limits") if accepted else None, "id": d.get("id") if accepted else None}
        print(f"{name:32} -> {st} {'ACCEPTED ' + d['id'] if accepted else (msg or '')[:110]}")
    # raw NaN (not valid JSON) sent as bytes
    import json as _j
    raw = _j.dumps(B(limits={"max_runtime_seconds": float("nan"), "max_cost_usd": 0.05}))
    r = m.s.post(f"{__import__('client').BASE_URL}/tasks", data=raw,
                 headers={"Authorization": f"Bearer {m.token}", "Content-Type": "application/json"}, timeout=60)
    res["runtime_NaN_raw"] = {"status": r.status_code, "body": r.text[:300]}
    print(f"{'runtime_NaN_raw':32} -> {r.status_code} {r.text[:110]}")
    if r.status_code == 202:
        m.call("POST", f"/tasks/{r.json()['id']}/cancel", label="edge-cleanup")
    return res


def happy(m):
    body = {"goal": "Open the page and report the main heading text and the first link's URL.",
            "environment": ENV, "model": "moss-fast", "effort": "low",
            "limits": {"max_runtime_seconds": 300, "max_cost_usd": 0.5}}
    t0 = time.time()
    st, d, _, create_s = create(m, body, label="happy-create")
    print("create:", st, round(create_s, 2), "s")
    if st != 202:
        return {"create_status": st, "body": d}
    st2, final, trail = poll(m, d["id"])
    files = m.call("GET", f"/tasks/{d['id']}/files", label="happy-files")[:2]
    r = {"create_status": st, "create_latency_s": create_s, "wall_s": round(time.time() - t0, 1),
         "status_trail": trail, "final": summarize(final), "files": files}
    print(r)
    return r


def schema(m):
    body = {"goal": "Return the page title and whether the page mentions the word 'domain'.",
            "environment": ENV, "model": "moss-fast", "effort": "low",
            "output_schema": {"type": "object",
                              "properties": {"title": {"type": "string"}, "mentions_domain": {"type": "boolean"}},
                              "required": ["title", "mentions_domain"]},
            "limits": {"max_runtime_seconds": 300, "max_cost_usd": 0.5}}
    st, d, _, _ = create(m, body, label="schema-create")
    if st != 202:
        return {"create_status": st, "body": d}
    _, final, trail = poll(m, d["id"])
    r = {"status_trail": trail, "final": summarize(final)}
    print(r)
    return r


def idempotency(m):
    key = str(uuid.uuid4())
    body = {"goal": "Report the page title.", "environment": ENV, "model": "moss-fast", "effort": "low",
            "limits": {"max_runtime_seconds": 120, "max_cost_usd": 0.25}}
    a = create(m, body, key, "idem-1")
    b = create(m, body, key, "idem-2")
    body2 = dict(body, goal="A different goal with the same key.")
    c = create(m, body2, key, "idem-3-different-body")
    ids = [x[1].get("id") if isinstance(x[1], dict) else None for x in (a, b, c)]
    for tid in {i for i in ids if i}:
        m.call("POST", f"/tasks/{tid}/cancel", label="idem-cleanup")
    r = {"statuses": [a[0], b[0], c[0]], "ids": ids, "same_id_on_replay": ids[0] == ids[1],
         "different_body_response": c[1] if ids[2] != ids[0] else "returned original task"}
    print(r)
    return r


def cancel(m):
    body = {"goal": "Browse example.com and describe every link, then follow each one.",
            "environment": ENV, "model": "moss-fast", "limits": {"max_runtime_seconds": 120, "max_cost_usd": 0.25}}
    st, d, _, _ = create(m, body, label="cancel-create")
    if st != 202:
        return {"create_status": st, "body": d}
    time.sleep(3)
    cs = m.call("POST", f"/tasks/{d['id']}/cancel", label="cancel")
    _, final, trail = poll(m, d["id"], every=2, max_wait=120)
    again = m.call("POST", f"/tasks/{d['id']}/cancel", label="cancel-again")[:2]
    early_files = m.call("GET", f"/tasks/{d['id']}/files", label="cancel-files")[:2]
    r = {"cancel_response": cs[:2], "status_trail": trail, "final": summarize(final),
         "cancel_twice": again, "files_after_cancel": early_files}
    print(r)
    return r


def limits(m):
    res = {}
    hard = ("Research the five most-starred Python web frameworks on GitHub, visit each repo, and "
            "compare their README install steps in detail.")
    for name, lim in {"tiny_budget": {"max_cost_usd": 0.01, "max_runtime_seconds": 300},
                      "tiny_runtime": {"max_cost_usd": 0.5, "max_runtime_seconds": 60}}.items():
        st, d, _, _ = create(m, {"goal": hard, "environment": {"type": "browser", "start_url": "https://github.com"},
                                 "model": "moss-fast", "limits": lim}, label=f"limits-{name}")
        if st != 202:
            res[name] = {"create_status": st, "body": d}
            continue
        _, final, trail = poll(m, d["id"], every=5, max_wait=400)
        res[name] = {"status_trail": trail, "final": summarize(final)}
        print(name, res[name])
    return res


def queue(m):
    ids, statuses = [], []
    body = {"goal": "Wait on the page.", "environment": ENV, "model": "moss-fast",
            "limits": {"max_runtime_seconds": 60, "max_cost_usd": 0.05}}
    try:
        for i in range(25):
            st, d, hdr, _ = create(m, body, label=f"queue-{i}")
            statuses.append(st)
            if st == 202:
                ids.append(d["id"])
            else:
                print("first non-202 at", i, st, d, "Retry-After:", hdr.get("Retry-After"))
                break
    finally:
        for tid in ids:
            m.call("POST", f"/tasks/{tid}/cancel", label="queue-cleanup")
    return {"statuses": statuses, "accepted": len(ids)}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "validation"
    fns = {"validation": validation, "edges": edges, "happy": happy, "schema": schema, "idempotency": idempotency,
           "cancel": cancel, "limits": limits, "queue": queue}
    names = [n for n in fns if n != "queue"] if which == "all" else [which]
    m = Moss("tasks")
    results = {n: fns[n](m) for n in names}
    save_result("tasks_" + which, results)


if __name__ == "__main__":
    main()
