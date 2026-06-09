import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

Deno.serve(async (req) => {
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, content-type",
  };

  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  // Verify caller is authenticated
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return Response.json({ error: "Unauthorized" }, { status: 401, headers: corsHeaders });

  const userSb = createClient(SUPABASE_URL, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: { user }, error: authErr } = await userSb.auth.getUser();
  if (authErr || !user) return Response.json({ error: "Unauthorized" }, { status: 401, headers: corsHeaders });

  const { handle, code } = await req.json();
  if (!handle || !code) return Response.json({ error: "Missing handle or code" }, { status: 400, headers: corsHeaders });

  // Fetch RSI profile page and look for the verify code in the bio
  let bio = "";
  try {
    const rsiUrl = `https://robertsspaceindustries.com/citizens/${encodeURIComponent(handle)}`;
    const res = await fetch(rsiUrl, {
      headers: { "User-Agent": "MiningSC-Verifier/1.0" },
    });
    const html = await res.text();

    // RSI bio is inside <div class="bio"> ... </div>
    const bioMatch = html.match(/<div[^>]+class="[^"]*bio[^"]*"[^>]*>([\s\S]*?)<\/div>/i);
    bio = bioMatch ? bioMatch[1].replace(/<[^>]+>/g, "") : "";

    // Also check the full page text in case markup differs
    if (!bio.includes(code)) {
      const pageText = html.replace(/<[^>]+>/g, " ");
      bio = pageText;
    }
  } catch (e) {
    return Response.json({ verified: false, error: "Could not reach RSI website" }, { headers: corsHeaders });
  }

  if (!bio.includes(code)) {
    return Response.json({ verified: false, error: "Code not found in RSI profile" }, { headers: corsHeaders });
  }

  // Mark player as verified
  const sb = createClient(SUPABASE_URL, SERVICE_KEY);
  const { error: updateErr } = await sb.from("players")
    .update({ sc_verified: true, verify_code: null })
    .eq("auth_id", user.id)
    .eq("verify_code", code);

  if (updateErr) return Response.json({ verified: false, error: updateErr.message }, { headers: corsHeaders });

  return Response.json({ verified: true }, { headers: corsHeaders });
});
