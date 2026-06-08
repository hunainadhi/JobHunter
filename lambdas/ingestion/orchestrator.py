import json
import boto3

WORKER_FUNCTION = "jobhunter-ingestion"

MATRIX = [
    {"ats_platform": "greenhouse", "chunk_index": 0, "total_chunks": 3},
    {"ats_platform": "greenhouse", "chunk_index": 1, "total_chunks": 3},
    {"ats_platform": "greenhouse", "chunk_index": 2, "total_chunks": 3},
    {"ats_platform": "ashby", "chunk_index": 0, "total_chunks": 2},
    {"ats_platform": "ashby", "chunk_index": 1, "total_chunks": 2},
    {"ats_platform": "lever", "chunk_index": 0, "total_chunks": 2},
    {"ats_platform": "lever", "chunk_index": 1, "total_chunks": 2},
    {"ats_platform": "workable", "chunk_index": 0, "total_chunks": 3},
    {"ats_platform": "workable", "chunk_index": 1, "total_chunks": 3},
    {"ats_platform": "workable", "chunk_index": 2, "total_chunks": 3},
    {"ats_platform": "smartrecruiters", "chunk_index": 0, "total_chunks": 2},
    {"ats_platform": "smartrecruiters", "chunk_index": 1, "total_chunks": 2},
    # Board scrapers
    {"ats_platform": "ycombinator", "board_scraper": True},
    {"ats_platform": "themuse", "board_scraper": True},
    {"ats_platform": "weworkremotely", "board_scraper": True},
    # Workday (25 companies split into 3 parallel chunks)
    {"ats_platform": "workday", "chunk_index": 0, "total_chunks": 3},
    {"ats_platform": "workday", "chunk_index": 1, "total_chunks": 3},
    {"ats_platform": "workday", "chunk_index": 2, "total_chunks": 3},
]


def lambda_handler(event, context):
    client = boto3.client("lambda", region_name="ca-central-1")

    for job in MATRIX:
        client.invoke(
            FunctionName=WORKER_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps(job),
        )
        if job.get("board_scraper"):
            print(f"Launched: {job['ats_platform']} (board)")
        else:
            print(f"Launched: {job['ats_platform']} chunk {job.get('chunk_index', 0)}/{job.get('total_chunks', 1)}")

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "launched", "workers": len(MATRIX)}),
    }
