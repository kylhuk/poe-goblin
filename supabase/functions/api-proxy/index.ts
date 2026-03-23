import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

import { rewriteProxySetCookie } from "./cookies.ts";
import { buildForwardHeaders, getCorsHeaders } from "./contract.ts";

const API_BASE = "https://api.poe.lama-lan.ch";

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
    /^\/api\/v1\/ml\/leagues\/[^/]+\/predict-one/.test(proxyPath) ||
    /^\/api\/v1\/auth\//.test(proxyPath);

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

  const forwardHeaders = buildForwardHeaders({
    existingCookie: req.headers.get("cookie") || "",
  });
  if (apiKey) {
    forwardHeaders["Authorization"] = `Bearer ${apiKey}`;
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

    // Forward set-cookie from backend
    const setCookie = backendRes.headers.get("set-cookie");
    if (setCookie) {
      responseHeaders.set("set-cookie", rewriteProxySetCookie(setCookie));
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
