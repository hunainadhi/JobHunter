import csv
import json
from pathlib import Path

import boto3

WORKER_FUNCTION = "jobhunter-ingestion"
DATA_DIR = Path(__file__).parent / "data"
BATCH_SIZE = 40

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

BOARD_SCRAPERS = ["ycombinator", "themuse", "weworkremotely"]


def load_company_count(ats_platform: str) -> int:
    csv_path = DATA_DIR / f"{ats_platform}.csv"
    if not csv_path.exists():
        return 0
    with open(csv_path) as f:
        return sum(1 for _ in csv.reader(f)) - 1


def lambda_handler(event, context):
    client = boto3.client("lambda", region_name="ca-central-1")

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

    # One throttled/failed invoke must not abort the remaining fan-out.
    launched = 0
    failed = 0
    for job in jobs:
        try:
            client.invoke(
                FunctionName=WORKER_FUNCTION,
                InvocationType="Event",
                Payload=json.dumps(job),
            )
            launched += 1
        except Exception as e:
            failed += 1
            print(f"Failed to launch worker {job}: {e}")

    print(f"Launched {launched}/{len(jobs)} ingestion workers ({failed} failed)")

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "launched", "workers": launched, "failed": failed}),
    }
