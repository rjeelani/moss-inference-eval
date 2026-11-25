# Moss Inference work sample

These are the scripts I used to test the Moss portal, the Inference API and the Tasks API, plus the raw logs they made. My write up is in ONE_PAGER.md. More detail on each finding is in notes/details.md.

I tested on Nov 24, 2026 from Toronto on the free Developer plan. Total spend was about 13 cents.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Make a file called .env in this folder with your keys. It is ignored by git.

```
MOSS_PROJECT_ID=your project id
MOSS_PROJECT_KEY=your project key
```

## Repros (start here)

Each one is a short script for one bug. Each prints what it expected and what it got. My own output is in repros/output.

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
| 02 | A cache hit returns the same text but a different output token count | under 0.1 cent |
| 03 | cancel_requested goes back to false after the task is cancelled | about 1 cent |
| 04 | A time limit of 60.5 is saved as 60 with no error | close to 0 |

## Full test scripts

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

Every call gets saved to logs as one JSON line, with the request, status, headers, response and time. The Authorization header is never saved. Summaries go in results.

## Folders

* harness: the full test scripts
* repros: one short script per bug, and my output
* logs: every request and response
* results: summary of each test run
* results/inference_run1_cached.json: my first benchmark, which was mostly cache hits. I kept it on purpose.
* results/happy_screens: the three identical screenshots one task returned
* notes/details.md: every finding in more detail
