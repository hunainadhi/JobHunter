"""One-time backfill: generate OpenAI text-embedding-3-small embeddings for all jobs missing them."""

import os
import time

import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BATCH_SIZE = 50
RPM_LIMIT = 90


def build_embed_text(job: dict) -> str:
    parts = [job["title"]]
    if job.get("company_name"):
        parts.append(f"at {job['company_name']}")
    if job.get("location"):
        parts.append(f"in {job['location']}")
    return " ".join(parts)


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-small", "input": texts},
        )
        resp.raise_for_status()
    data = resp.json()["data"]
    return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]


def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    total_embedded = 0
    interval = 60.0 / RPM_LIMIT

    while True:
        resp = (
            supabase.table("jobs")
            .select("id, title, company_name, location")
            .is_("embedding", "null")
            .limit(BATCH_SIZE)
            .execute()
        )

        jobs = resp.data
        if not jobs:
            break

        texts = [build_embed_text(j) for j in jobs]

        for attempt in range(5):
            try:
                embeddings = generate_embeddings(texts)
                break
            except Exception as e:
                wait = 15 * (attempt + 1)
                print(f"Embedding API error (attempt {attempt+1}/5): {e} — retrying in {wait}s", flush=True)
                time.sleep(wait)
        else:
            print("Failed after 5 attempts, skipping batch", flush=True)
            continue

        for job, emb in zip(jobs, embeddings):
            supabase.table("jobs").update({"embedding": emb}).eq("id", job["id"]).execute()

        total_embedded += len(jobs)
        print(f"Embedded {total_embedded} jobs...", flush=True)
        time.sleep(interval)

    print(f"Done. Total embedded: {total_embedded}")


if __name__ == "__main__":
    main()
