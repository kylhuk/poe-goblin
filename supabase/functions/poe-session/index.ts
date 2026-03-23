import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
};

// --- AES-GCM helpers ---
const ENC_KEY_HEX = Deno.env.get("POE_SESSION_ENCRYPTION_KEY")!;

async function getKey(): Promise<CryptoKey> {
  const raw = new Uint8Array(ENC_KEY_HEX.match(/.{2}/g)!.map((b) => parseInt(b, 16)));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

async function encrypt(plaintext: string): Promise<string> {
  const key = await getKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(plaintext))
  );
  // Store as base64(iv + ciphertext)
  const combined = new Uint8Array(iv.length + enc.length);
  combined.set(iv);
  combined.set(enc, iv.length);
  return btoa(String.fromCharCode(...combined));
}

async function decrypt(encoded: string): Promise<string> {
  const key = await getKey();
  const combined = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
  const iv = combined.slice(0, 12);
  const data = combined.slice(12);
  const dec = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, data);
  return new TextDecoder().decode(dec);
}

// --- Auth helper ---
async function getAuthedUser(req: Request) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) return null;
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } }
  );
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) return null;
  return { user, supabase };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  const auth = await getAuthedUser(req);
  if (!auth) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const { user, supabase } = auth;
  const serviceClient = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  try {
    // POST: save encrypted session
    if (req.method === "POST") {
      const { poeSessionId, accountName } = await req.json();
      if (!poeSessionId || typeof poeSessionId !== "string") {
        return new Response(JSON.stringify({ error: "Missing poeSessionId" }), {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const encrypted = await encrypt(poeSessionId);
      const { error } = await serviceClient
        .from("user_poe_sessions")
        .upsert(
          { user_id: user.id, encrypted_session: encrypted, account_name: accountName || null },
          { onConflict: "user_id" }
        );
      if (error) {
        return new Response(JSON.stringify({ error: "Failed to save session" }), {
          status: 500,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // GET: retrieve decrypted session
    if (req.method === "GET") {
      const { data, error } = await serviceClient
        .from("user_poe_sessions")
        .select("encrypted_session, account_name")
        .eq("user_id", user.id)
        .maybeSingle();
      if (error || !data) {
        return new Response(JSON.stringify({ poeSessionId: null, accountName: null }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const decrypted = await decrypt(data.encrypted_session);
      return new Response(
        JSON.stringify({ poeSessionId: decrypted, accountName: data.account_name }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // DELETE: remove session
    if (req.method === "DELETE") {
      await serviceClient.from("user_poe_sessions").delete().eq("user_id", user.id);
      return new Response(JSON.stringify({ ok: true }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "Internal error", message: err instanceof Error ? err.message : "Unknown" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
