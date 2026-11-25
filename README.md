# Moss Inference work sample

Hey! This is everything I ran while trying out Moss Inference for my work sample. I tested the portal, the Inference API and the Tasks API, and I kept all the raw logs so you can see exactly what happened.

My write up is in ONE_PAGER.md. If you want more detail on any finding, it's in notes/details.md.

I did all of this on Nov 24, 2026 from Toronto on the free Developer plan. It cost about 13 cents total.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then make a file called .env in this folder with your keys (git ignores it):

```
MOSS_PROJECT_ID=your project id
MOSS_PROJECT_KEY=your project key
```

## Repros (best place to start)

I made one short script for each bug I found. Each one prints what I expected and what actually happened. My own output from running them is in repros/output.

```powershell
cd repros
python 01_refused_request_not_in_logs.py
python 02_cache_hit_changes_token_count.py
python 03_cancel_requested_resets.py
python 04_runtime_decimal_silently_cut.py
```

| Script | What it shows | Cost |
|---|---|---|
| 01 | A refused request gives you a request ID that Logs can't find | free |
| 02 | A cache hit gives back the same text but a different output token count | under 0.1 cent |
| 03 | cancel_requested goes back to false after the task is cancelled | about 1 cent |
| 04 | A time limit of 60.5 gets saved as 60 with no error | close to 0 |

## Full test scripts

These are the bigger scripts I used to test everything.

```powershell
python harness/inference_probe.py --n 20 --burst 15
python harness/tasks_probe.py validation
python harness/tasks_probe.py edges
python harness/tasks_probe.py happy
python harness/tasks_probe.py schema
python harness/tasks_probe.py idempotency
python harness/tasks_probe.py cancel
python harness/tasks_probe.py limits
python harness/tasks_probe.py queue
```

Every call gets saved to the logs folder as one JSON line (request, status, headers, response and time). The Authorization header never gets saved. Short summaries of each run go in results.

## What's in each folder

* harness: the full test scripts
* repros: one short script per bug, plus my output
* logs: every request and response I sent
* results: a summary of each test run
* results/inference_run1_cached.json: my first benchmark, which turned out to be mostly cache hits. I kept it on purpose since it's part of what I learned.
* results/happy_screens: three screenshots from one task that turned out to be the exact same file
* notes/details.md: every finding in more detail, with where the proof is
