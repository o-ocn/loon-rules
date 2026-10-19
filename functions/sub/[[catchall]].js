const VMISS_SUB_ORIGIN = "https://38-207-167-188.sslip.io:8443";

export async function onRequest(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  const parts = Array.isArray(params.catchall) ? params.catchall : (params.catchall || "").split("/");
  // Only the two subscription resources linked by the unlock interface are proxied.
  if (parts.length !== 2 || !/^[A-Za-z0-9_-]{16,128}$/.test(parts[0]) ||
      !["loon.txt", "clash.yaml"].includes(parts[1]) || url.search) {
    return new Response("Invalid subscription path", { status: 404, headers: { "Cache-Control": "no-store" } });
  }
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: {
      "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS"
    } });
  }
  if (!["GET", "HEAD"].includes(request.method)) {
    return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD, OPTIONS" } });
  }
  const upstreamUrl = VMISS_SUB_ORIGIN + "/" + parts.map(encodeURIComponent).join("/");
  const headers = new Headers();
  for (const name of ["Accept", "User-Agent"]) {
    if (request.headers.has(name)) headers.set(name, request.headers.get(name));
  }
  try {
    const upstreamResponse = await fetch(upstreamUrl, { method: request.method, headers, redirect: "manual" });
    if (upstreamResponse.status >= 300 && upstreamResponse.status < 400) {
      return new Response("Subscription redirect rejected", { status: 502, headers: { "Cache-Control": "no-store" } });
    }
    const respHeaders = new Headers();
    for (const name of ["Content-Type", "Content-Disposition", "Subscription-Userinfo", "Profile-Update-Interval"]) {
      if (upstreamResponse.headers.has(name)) respHeaders.set(name, upstreamResponse.headers.get(name));
    }
    respHeaders.set("Access-Control-Allow-Origin", "*");
    respHeaders.set("X-Gateway-By", "Cloudflare-Pages-Edge-Sub");
    respHeaders.set("Cache-Control", "no-store");
    return new Response(request.method === "HEAD" ? null : upstreamResponse.body, {
      status: upstreamResponse.status, headers: respHeaders
    });
  } catch (_error) {
    return new Response("Subscription upstream unavailable", { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
