# Moss Inference work sample, Rahim Jeelani

Repo: <GITHUB LINK>

The repo has my scripts, raw logs, and a repros folder with one short script per bug so you can rerun them. I spent about 13 cents in total.

## 1. Portal

**What I liked.** The Playground shows first token time, total time, tokens and a request ID under every reply. The New task form has a Get code button that turns the form into SDK code.

**What I didn't like.** Refused requests don't show up in Logs. The docs say every response has a request ID, including refused ones, and to send that ID when reporting a problem. I made about 30 refused calls, mostly 429s. Logs still said Errors 0%, and searching for one of those IDs said no request with that ID in the last 30 days. A normal request sent seconds later did show up, so it wasn't a delay. I also couldn't find my remaining credit on the Usage or Billing pages.

**What I would improve.** Log refused requests so their IDs can be found, and show the credit balance on the Usage page.

## 2. Inference API

**What I liked.** It works like the OpenAI API, so plain HTTP calls just worked. On fastlane-1 the median time was 355 ms over 20 different prompts, and the first streamed token came at 107 ms. The rate limit matched the docs. I sent 15 calls at once and got 11 through and 4 rate limited, with correct Retry-After headers.

**What I didn't like.** The reply cache fooled me at first. My first benchmark said 55 ms, but 9 of the 10 calls were cache hits because I reused the same prompt. The cache is in the docs, but it is on by default and the only sign of a hit is input tokens being 0. A cache hit also returns the same text with a different output token count. In three tries it went from 30 to 39, 35 to 52, and 31 to 40.

**What I would improve.** Add a header that says cache hit or miss, return the same token count for the same reply, and tell people in the docs to turn the cache off when benchmarking.

## 3. Tasks API

**What I tested.** 30 bad or edge case requests, a normal task, an output schema, idempotency keys, cancel, the budget and time limits, and 25 tasks at once.

**Results.** All three tasks with an answer I could check were correct, including Toronto's 2021 population (2,794,356). Each took about 20 seconds and cost under 6 cents. Idempotency worked exactly right, and the same key with a different body got a 422. Input checking was the best part. Every bad request except one got a clear error. A 1 cent budget stopped at 1.01 cents and a 60 second limit stopped at 61 seconds.

**Where I broke it.**
1. cancel_requested goes back to false once a task is cancelled, even though the docs describe it as whether a cancel was requested. Cancelled tasks also come back in two different shapes. Some have cost 0 and no error, others have no cost and a cancelled error.
2. A time limit of 60.5 is accepted and saved as 60 with no warning, but "60" as a string gets an error.
3. Error messages list things that are not in the docs, like the moss-fast-beta model (which does run tasks) and a proxy_country setting.
4. The docs say browser time is rounded up to the minute, but a 61 second run was billed as 1 minute.
5. All 25 tasks started right away, so I couldn't reach the 20 task queue limit. My plan says 1 concurrent session, and the docs don't say if that applies to tasks.

**What I would improve.** Keep cancel_requested true and use one shape for cancelled tasks. Reject decimal time limits. Either document the beta models and settings or keep them out of error messages.
