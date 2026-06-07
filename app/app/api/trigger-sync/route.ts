import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.SYNC_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const lambdaUrl = process.env.LAMBDA_FUNCTION_URL;
  if (!lambdaUrl) {
    return NextResponse.json(
      { error: "LAMBDA_FUNCTION_URL not configured" },
      { status: 500 }
    );
  }

  try {
    // Fire-and-forget: don't await the full Lambda execution
    // Just confirm Lambda accepted the request
    fetch(lambdaUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.SYNC_SECRET}`,
      },
      body: JSON.stringify({
        trigger: "cron",
        timestamp: new Date().toISOString(),
      }),
    }).catch((err) => {
      console.error("Lambda invocation error (background):", err);
    });

    return NextResponse.json({ status: "sync triggered" });
  } catch (error) {
    console.error("Sync trigger failed:", error);
    return NextResponse.json({ error: "Sync failed" }, { status: 500 });
  }
}
