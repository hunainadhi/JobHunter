import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export async function GET() {
  const { count } = await supabase
    .from("jobs")
    .select("id", { count: "exact", head: true });

  return NextResponse.json({ status: "ok", jobs_count: count });
}
