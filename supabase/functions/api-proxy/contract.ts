export function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers":
      "authorization, x-client-info, apikey, content-type, x-proxy-path",
    "Access-Control-Allow-Credentials": "true",
  };
}

export function buildForwardHeaders({
  existingCookie,
}: {
  existingCookie: string;
}): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (existingCookie) {
    headers["Cookie"] = existingCookie;
  }
  return headers;
}
