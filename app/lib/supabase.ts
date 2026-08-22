import { createClient } from "@supabase/supabase-js";
import { getSupabaseReadConfig } from "./supabase-config";

const { url, key } = getSupabaseReadConfig();

export const supabase = createClient(url, key);
