"""Probe the Moss Inference API: latency, streaming TTFT, error shapes, burst limits.

Usage: python harness/inference_probe.py [--n 10] [--burst 15] [--model moss/fastlane-1]
Costs are small (short prompts, max_output_tokens capped).
"""
import argparse
import concurrent.futures as cf
import json
import statistics
import time
import uuid

from client import Moss, save_result

PROMPT = {"instructions": "Answer in one short sentence.", "input": "What is a semantic index?"}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--burst", type=int, default=15)
    ap.add_argument("--model", default="moss/fastlane-1")
    a = ap.parse_args()
    m = Moss("inference")
    out = {"model": a.model}

    # 1. models
    st, data, _, el = m.call("GET", "/models", label="models")
    out["models"] = {"status": st, "elapsed_s": el,
                     "ids": [x.get("id") for x in data.get("data", [])] if isinstance(data, dict) else data}
    print("models:", out["models"]["ids"])

    run_id = uuid.uuid4().hex[:8]  # makes every prompt unique so the reply cache can't serve it

    def cooldown():
        time.sleep(6)  # burst bucket (10) refills ~2/s; let it fill before the next section

    # 2. sequential latency, UNIQUE prompts (uncached), paced under 2 req/s
    lat = []
    for i in range(a.n):
        body = {"model": a.model, "instructions": PROMPT["instructions"],
                "input": f"[{run_id}-{i}] What is a semantic index?", "max_output_tokens": 64}
        st, data, hdr, el = m.call("POST", "/responses", body, label=f"resp-{i}")
        if st == 200:
            lat.append(el)
        else:
            print("non-200:", st, data)
        time.sleep(0.6)
    out["responses_latency_s"] = {"n": len(lat), "median": statistics.median(lat),
                                  "p90": pct(lat, 0.9), "min": min(lat), "max": max(lat)}
    out["ratelimit_headers_sample"] = {k: v for k, v in hdr.items() if k.lower().startswith("x-ratelimit")}
    print("uncached latency:", out["responses_latency_s"])
    cooldown()

    # 2b. reply cache: same prompt twice; compare latency, text, usage
    body = {"model": a.model, **PROMPT, "input": f"[{run_id}-cache] What is a semantic index?",
            "max_output_tokens": 64}
    c = [m.call("POST", "/responses", body, label=f"cache-{j}") for j in range(2)]
    txt = lambda d: "".join(x.get("text", "") for o in d.get("output", []) for x in o.get("content", []))
    out["reply_cache"] = {"latency_s": [c[0][3], c[1][3]], "same_text": txt(c[0][1]) == txt(c[1][1]),
                          "usage": [c[0][1].get("usage"), c[1][1].get("usage")],
                          "cache_headers": [{k: v for k, v in x[2].items() if "cache" in k.lower()} for x in c]}
    print("reply cache:", out["reply_cache"])
    cooldown()

    # 3. streaming: time to first delta vs total (unique prompt)
    r, t0 = m.call("POST", "/responses", {"model": a.model, "instructions": PROMPT["instructions"],
                                          "input": f"[{run_id}-stream] Explain a semantic index in two sentences.",
                                          "stream": True, "max_output_tokens": 96},
                   stream=True, label="stream")
    first = None
    events = 0
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            events += 1
            if first is None and "output_text.delta" in line:
                first = time.perf_counter() - t0
    out["streaming"] = {"status": r.status_code, "ttft_s": first,
                        "total_s": time.perf_counter() - t0, "events": events}
    print("streaming:", out["streaming"])
    cooldown()

    # 4. chat completions
    st, data, _, el = m.call("POST", "/chat/completions",
                             {"model": a.model, "max_tokens": 32,
                              "messages": [{"role": "user", "content": "Say hi."}]}, label="chat")
    out["chat_completions"] = {"status": st, "elapsed_s": el}
    print("chat:", st, round(el, 3))

    # 5. error shapes
    errs = {}
    bad = Moss("inference")
    bad.token = "bad:bad"
    errs["bad_key"] = bad.call("POST", "/responses", {"model": a.model, **PROMPT}, label="err-badkey")[:2]
    errs["unknown_model"] = m.call("POST", "/responses", {"model": "nope/nope", **PROMPT}, label="err-model")[:2]
    errs["missing_input"] = m.call("POST", "/responses", {"model": a.model}, label="err-noinput")[:2]
    errs["unknown_index"] = m.call("POST", "/responses", {"model": a.model, **PROMPT},
                                   headers={"X-Moss-Indexes": "does-not-exist-xyz"}, label="err-index")[:2]
    errs["empty_body"] = m.call("POST", "/responses", {}, label="err-empty")[:2]
    out["errors"] = {k: {"status": v[0], "body": v[1]} for k, v in errs.items()}
    for k, v in out["errors"].items():
        print("error", k, v["status"], json.dumps(v["body"])[:160])
    cooldown()

    # 6. burst: fire N concurrent requests, count 429s (docs: burst 10 on fastlane)
    def one(i):
        st, data, hdr, el = m.call("POST", "/responses",
                                   {"model": a.model, "instructions": PROMPT["instructions"],
                                    "input": f"[{run_id}-burst-{i}] Say ok.", "max_output_tokens": 16},
                                   label=f"burst-{i}")
        return st, hdr.get("Retry-After") or hdr.get("retry-after"), el

    with cf.ThreadPoolExecutor(a.burst) as ex:
        res = list(ex.map(one, range(a.burst)))
    out["burst"] = {"sent": a.burst, "ok": sum(r[0] == 200 for r in res),
                    "429": sum(r[0] == 429 for r in res), "other": [r[0] for r in res if r[0] not in (200, 429)],
                    "retry_after_seen": [r[1] for r in res if r[1]]}
    print("burst:", out["burst"])

    save_result("inference", out)


if __name__ == "__main__":
    main()
