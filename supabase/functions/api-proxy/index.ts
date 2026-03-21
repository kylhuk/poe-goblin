import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

import { rewriteProxySetCookie } from "./cookies.ts";

const API_BASE = "https://api.poe.lama-lan.ch";

function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers":
      "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version, x-proxy-path, x-poe-session, x-poe-backend-session",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Credentials": "true",
  };
}

Deno.serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);

  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  // 0. Get the target path early for public endpoint check
  const proxyPath = req.headers.get("x-proxy-path");
  if (!proxyPath) {
    return new Response(JSON.stringify({ error: "Missing x-proxy-path header" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Public endpoints that don't require auth (ML Price)
  const isPublicEndpoint =
    /^\/api\/v1\/ops\/leagues\/[^/]+\/price-check/.test(proxyPath) ||
    /^\/api\/v1\/ml\/leagues\/[^/]+\/predict-one/.test(proxyPath);

  // 1. Validate Supabase JWT (skip for public endpoints)
  const authHeader = req.headers.get("authorization");

  if (!isPublicEndpoint) {
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseAnonKey, {
      global: { headers: { Authorization: authHeader } },
    });

    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 2. Check approval status
    const { data: approval } = await supabase
      .from("approved_users")
      .select("id")
      .eq("user_id", user.id)
      .maybeSingle();

    if (!approval) {
      return new Response(JSON.stringify({ error: "Account not approved" }), {
        status: 403,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
  }

  // 3. Forward request to backend with server-side API key
  const apiKey = Deno.env.get("VITE_API_KEY");
  const targetUrl = `${API_BASE}${proxyPath}`;

  const forwardHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    forwardHeaders["Authorization"] = `Bearer ${apiKey}`;
  }

  // Build cookie string from custom headers
  const poeSession = req.headers.get("x-poe-session");
  const poeBackendSession = req.headers.get("x-poe-backend-session");
  const existingCookie = req.headers.get("cookie") || "";

  const cookieParts: string[] = [];
  if (existingCookie) cookieParts.push(existingCookie);
  if (poeSession) cookieParts.push(`POESESSID=${poeSession}`);
  if (poeBackendSession) cookieParts.push(`poe_session=${poeBackendSession}`);

  if (cookieParts.length > 0) {
    forwardHeaders["Cookie"] = cookieParts.join("; ");
  }

  try {
    const body = req.method !== "GET" && req.method !== "HEAD" ? await req.text() : undefined;

    const backendRes = await fetch(targetUrl, {
      method: req.method,
      headers: forwardHeaders,
      body,
    });

    const responseHeaders = new Headers(corsHeaders);
    responseHeaders.set("Content-Type", backendRes.headers.get("Content-Type") || "application/json");

    // Extract poe_session cookie from backend set-cookie and expose it as a custom header
    const setCookie = backendRes.headers.get("set-cookie");
    if (setCookie) {
<<<<<<< HEAD
      responseHeaders.set("set-cookie", rewriteProxySetCookie(setCookie));
=======
      const match = setCookie.match(/poe_session=([^;]+)/);
      if (match) {
        responseHeaders.set("x-poe-backend-session", match[1]);
        // Expose this header to the browser
        responseHeaders.set("Access-Control-Expose-Headers", "x-poe-backend-session");
      }
>>>>>>> 11ba251db101db36f5c5d13e502a6c9588a25d30
    }

    const responseBody = await backendRes.arrayBuffer();
    return new Response(responseBody, {
      status: backendRes.status,
      headers: responseHeaders,
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "Backend request failed", message: err instanceof Error ? err.message : "Unknown error" }),
      { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
