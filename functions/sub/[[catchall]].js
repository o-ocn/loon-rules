const VMISS_SUB_ORIGIN = "https://38-207-167-188.sslip.io:8443";

export async function onRequest(context) {
  const { request, params } = context;
  const url = new URL(request.url);

  // params.catchall is an array of path segments after /sub/
  // e.g. ["03c12794a786246b181ffa52410f5fd0", "clash.yaml"]
  const subPath = Array.isArray(params.catchall)
    ? params.catchall.join("/")
    : (params.catchall || "");

  const upstreamUrl = `${VMISS_SUB_ORIGIN}/${subPath}${url.search}`;

  const headers = new Headers(request.headers);
  headers.set("Host", "38-207-167-188.sslip.io:8443");
  headers.set("X-Forwarded-Host", url.hostname);
  headers.set("X-Forwarded-Proto", "https");

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      redirect: "follow"
    });

    const respHeaders = new Headers(upstreamResponse.headers);
    respHeaders.set("Access-Control-Allow-Origin", "*");
    respHeaders.set("X-Gateway-By", "Cloudflare-Pages-Edge-Sub");

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: respHeaders
    });
  } catch (err) {
    return new Response(
      JSON.stringify({
        error: "Subscription Gateway Proxy Error",
        message: "无法连接上游订阅源，请稍后重试"
      }),
      {
        status: 502,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store"
        }
      }
    );
  }
}
