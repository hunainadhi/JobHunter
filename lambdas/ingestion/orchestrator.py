import csv
import json
import time
from datetime import date
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

WORKER_FUNCTION = "jobhunter-ingestion"
SELF_FUNCTION = "jobhunter-orchestrator"
DATA_DIR = Path(__file__).parent / "data"
BATCH_SIZE = 40

# The account's Lambda concurrency ceiling (measured at 50) is far below the
# ~500+ invocations a full day's worth of batches needs, so firing them all
# in one burst gets ~94% throttled instantly. Instead we dispatch in small
# waves, requeue anything throttled, and self-chain with a real pause between
# waves so the concurrency ceiling actually gets a chance to drain.
WAVE_SIZE = 40
INVOKE_STAGGER_SECONDS = 0.5
TARGET_CYCLE_SECONDS = 870  # ~14.5 min between wave starts, under the 900s Lambda ceiling
SAFETY_MARGIN_SECONDS = 30
MAX_CHAIN_DEPTH = 30  # generous headroom: 30 waves * 40 = 1,200 job-attempts/day

ATS_PLATFORMS = {
    "greenhouse": None,
    "lever": None,
    "ashby": None,
    "smartrecruiters": None,
    "workable": None,
    "rippling": None,
    "icims": None,
    "pinpoint": None,
    "teamtailor": None,
    "breezy": None,
}

BOARD_SCRAPERS = ["ycombinator", "weworkremotely"]
# themuse was removed upstream in jobhive (pure aggregator, no direct postings).


def load_company_count(ats_platform: str) -> int:
    csv_path = DATA_DIR / f"{ats_platform}.csv"
    if not csv_path.exists():
        return 0
    with open(csv_path) as f:
        return sum(1 for _ in csv.reader(f)) - 1


def build_job_list() -> list[dict]:
    jobs = []
    for platform in ATS_PLATFORMS:
        count = load_company_count(platform)
        for offset in range(0, count, BATCH_SIZE):
            jobs.append({
                "ats_platform": platform,
                "offset": offset,
                "batch_size": BATCH_SIZE,
            })

    for board in BOARD_SCRAPERS:
        jobs.append({"ats_platform": board, "board_scraper": True})

    # Rotate by a day-dependent offset so the front-of-queue advantage cycles
    # across all platforms/batches over days, complementing the in-day
    # requeue-based fairness below.
    if jobs:
        rotation = date.today().toordinal() % len(jobs)
        jobs = jobs[rotation:] + jobs[:rotation]

    return jobs


def is_throttling_error(e: Exception) -> bool:
    if isinstance(e, ClientError):
        return e.response.get("Error", {}).get("Code") == "TooManyRequestsException"
    return "TooManyRequestsException" in str(e) or "Rate Exceeded" in str(e)


def lambda_handler(event, context):
    client = boto3.client("lambda", region_name="ca-central-1")
    start_time = time.time()

    chain_depth = (event or {}).get("chain_depth", 0)
    remaining_jobs = (event or {}).get("remaining_jobs")
    jobs = remaining_jobs if remaining_jobs is not None else build_job_list()

    this_wave = jobs[:WAVE_SIZE]
    still_pending = jobs[WAVE_SIZE:]

    launched = 0
    requeued = 0
    failed = 0
    for job in this_wave:
        try:
            client.invoke(
                FunctionName=WORKER_FUNCTION,
                InvocationType="Event",
                Payload=json.dumps(job),
            )
            launched += 1
        except Exception as e:
            if is_throttling_error(e):
                still_pending.append(job)
                requeued += 1
            else:
                failed += 1
                print(f"Failed to launch worker {job}: {e}")
        time.sleep(INVOKE_STAGGER_SECONDS)

    print(
        f"Wave (depth={chain_depth}): launched={launched} requeued={requeued} "
        f"failed={failed} still_pending={len(still_pending)}"
    )

    if still_pending and chain_depth < MAX_CHAIN_DEPTH:
        elapsed = time.time() - start_time
        remaining_budget = (context.get_remaining_time_in_millis() / 1000) - SAFETY_MARGIN_SECONDS
        sleep_for = max(0, min(TARGET_CYCLE_SECONDS - elapsed, remaining_budget))
        print(f"Sleeping {sleep_for:.0f}s before next wave (chain depth {chain_depth + 1})")
        time.sleep(sleep_for)

        client.invoke(
            FunctionName=SELF_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps({
                "remaining_jobs": still_pending,
                "chain_depth": chain_depth + 1,
            }),
        )
    elif still_pending:
        print(f"NOT self-chaining: hit depth cap with {len(still_pending)} jobs never dispatched today")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "wave_complete",
            "chain_depth": chain_depth,
            "launched": launched,
            "requeued": requeued,
            "failed": failed,
            "still_pending": len(still_pending),
        }),
    }
