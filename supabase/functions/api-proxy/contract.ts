export function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers":
      "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version, x-proxy-path, x-poe-backend-session",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Credentials": "true",
  };
}

export function buildForwardHeaders(params: {
  existingCookie: string;
}): Record<string, string> {
  const forwardHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (params.existingCookie) {
    forwardHeaders["Cookie"] = params.existingCookie;
  }
  return forwardHeaders;
}
