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
]


def lambda_handler(event, context):
    client = boto3.client("lambda", region_name="ca-central-1")

    for job in MATRIX:
        client.invoke(
            FunctionName=WORKER_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps(job),
        )
        print(f"Launched: {job['ats_platform']} chunk {job['chunk_index']}/{job['total_chunks']}")

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "launched", "workers": len(MATRIX)}),
    }
