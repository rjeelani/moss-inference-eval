# Details

These are my notes from testing on Nov 24, 2026. Each point says where the proof is.

## Portal

Signing in asked for a text message code first.

The home page is a chat box with three cards. The keys and setup steps are on the Configure page. The setup step uses export, which only works in bash, not PowerShell.

The Models page lists 19 models with prices. fastlane-1 costs 0.25 dollars in and 1.75 dollars out per million tokens. Some open models on the same page are cheaper, and the page doesn't say why fastlane is worth more.

Playground test: "In one sentence: what is a vector index?" on fastlane-1. It showed first token 121 ms, total 475 ms, 97 tokens in, 46 out. 97 input tokens for a 9 word question means about 85 tokens get added that I can't see. Logs showed the same request ID with first token 55 ms and total 416 ms.

Logs and refused requests. After about 30 refused calls, Logs still said Errors 0% and the Error filter was empty. I searched for a 429 ID (7aa11cde4e714ff5a89b55a1fabf1bfe), a 403 ID (505497da7fb7455da26fed7ed800a64f) and a 400 ID (f5709b5f68d04f89a0bc3634b2674e75). All three said no request with that ID in the last 30 days. A normal request sent a few seconds after the 400 did show up. The docs say every response has a request ID, refused ones included, and to send it when reporting a problem. Proof: logs/inference*.jsonl, repros/output/01_*.

Logs does label cache hits as "Cache hit", but the API response doesn't.

New task form: goal, start URL, model, and options for time, cost and output schema. The defaults are 30 minutes and 2 dollars, which is 20 percent of the signup credit. Get code turns the form into SDK code. While a task runs there is no live view. Screenshots only show up at the end.

Credits: the Plans page and the pricing docs say the Developer plan gets $10 once at signup. The Billing page under Settings shows a $10.00 balance and also "$0.13 of $5.00 monthly credit used, resets Dec 1". The $5 monthly credit isn't in the docs, and my spend came out of it, not the $10. Usage shows the total ($0.13) but not what's left. The Plans page says the Developer plan has 1 concurrent session.

Analytics shows Success rate 100% over 86 requests, so refused calls aren't counted there either.

## Inference API

Uncached speed on fastlane-1: median 355 ms, p90 419 ms, over 20 different prompts with up to 64 output tokens. Streaming first token: 107 ms. Proof: results/inference.json.

Responses and Chat Completions both worked. Errors use the OpenAI format and say what to do next.

Rate limit: the docs say a burst of 10, then about 2 per second. 15 calls at once gave 11 OK and 4 rate limited, each with Retry-After 1. In my first run I sent the burst right after 10 other calls, so only 3 got through. That was my mistake, not a bug.

Reply cache: this is in the docs. A hit costs nothing, shows 0 input tokens, and you can turn it off with the X-Moss-Cache header. I missed it at first. My first benchmark said 56 ms, but 9 of 10 calls were cache hits. What is not in the docs is that a hit reports a different output token count for the exact same text. I saw 35 to 52, 30 to 39, and 31 to 40. Proof: results/inference_run1_cached.json, results/inference.json, repros/output/02_*.

An index name that doesn't exist gets a 403 that says the index is outside this project. This matches the docs.

## Tasks API

Input checking: I sent 30 bad or edge case requests. These include a missing goal, a goal that is too long, wrong types, values out of range, unknown fields (also nested ones), a bad schema, NaN in the JSON, and a body over 256 KB. All got a clear 400 or 413 except a time limit of 60.5, which was saved as 60. Proof: results/tasks_validation.json, results/tasks_edges.json, repros/output/04_*.

Error messages show things that are not in the docs: the models moss-fast-beta and moss-balanced-handoff, and an environment setting called proxy_country. moss-fast-beta accepted a task. I searched the full docs text for all three and found nothing.

Normal task on example.com: done in 21 seconds for about half a cent, 3 steps. The answer was right. The page HTML has no heading, and the first link is iana.org/help/example-domains. I checked both myself. All three screenshot files it returned were the exact same file. Proof: results/tasks_happy.json, results/happy_screens.

Output schema task: returned title Example Domain and mentions_domain true, and the schema check passed. Proof: results/tasks_schema.json.

Portal task: Toronto's population from Wikipedia. It returned 2,794,356 for 2021, which is correct, in 21 seconds for about 6 cents.

Idempotency: the same key and body gave the same task back. The same key with a different body got a 422 that says the key was reused. Proof: results/tasks_idempotency.json.

Cancel: I cancelled 3 seconds in, and the task ended about 15 seconds later. The docs say a cancelled task still gets billed, so the cost is expected. cancel_requested was true right after cancel and false once the task ended. Cancelled tasks come back in two shapes. Some have cost 0 and no error, others have no cost and an error with code cancelled. Proof: results/tasks_cancel.json, repros/output/03_*.

Limits: the docs say the cost limit only counts model calls. A 1 cent budget failed with budget_exceeded at 1.01 cents of model spend. A 60 second limit failed with time_limit at 61 seconds. In both cases any partial answer is thrown away. Proof: results/tasks_limits.json.

Browser billing: the docs say 0.02 dollars per hour, billed per minute and rounded up. Runs under a minute cost 1 minute, which is right. The 61 second run also cost 1 minute, but rounding up should make it 2.

Queue: I sent 25 tasks quickly. All of them started running right away and none waited in the queue, so I never hit the 20 queued task limit. I cancelled all 25, and they cost under 1 cent together. Proof: results/tasks_queue.json.
