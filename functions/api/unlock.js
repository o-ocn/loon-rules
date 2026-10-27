const VAULT_SALT_HEX = "3210fdfd5e3fa478a72340ec9d153eec";
const VAULT_IV_HEX = "d51dfa6abe2d45d40f393e29";
const VAULT_CIPHER_WITH_TAG_HEX = "89da17b8209f1df1e6cc86408fb751593aa53eecb305881e65b401049a379d77ef0f0b1c983f6c726dba4feafbf0e646";

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

async function unlockVault(password) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(password),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );

  const key = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: hexToBytes(VAULT_SALT_HEX),
      iterations: 100000,
      hash: "SHA-256"
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );

  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: hexToBytes(VAULT_IV_HEX) },
    key,
    hexToBytes(VAULT_CIPHER_WITH_TAG_HEX)
  );

  return new TextDecoder().decode(decrypted);
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400"
    }
  });
}

export async function onRequestPost(context) {
  const { request } = context;
  const url = new URL(request.url);

  try {
    const body = await request.json();
    const password = (body.password || "").trim();
    const client = (body.client || "").toLowerCase();

    if (!password) {
      return new Response(
        JSON.stringify({ success: false, error: "请输入访问密码" }),
        {
          status: 400,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }

    let token;
    try {
      token = await unlockVault(password);
    } catch (_authErr) {
      return new Response(
        JSON.stringify({ success: false, error: "访问密码错误，请核对后重试" }),
        {
          status: 401,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }

    let subFile = "clash.yaml";
    let subUrl = "";
    let importUrl = "";
    let configUrl = "";
    let configImportUrl = "";

    // This gateway header is accepted only for our known public entry.
    const forwardedHost = request.headers.get("x-forwarded-host");
    const host = forwardedHost === "loon.rules.o-ous.com" ? forwardedHost : url.hostname;

    if (client === "loon" || host.startsWith("loon.")) {
      subFile = "loon.txt";
      subUrl = `https://${host}/sub/${token}/${subFile}`;
      importUrl = `loon://import?nodelist=${encodeURIComponent(subUrl)}`;
      configUrl = `https://${host}/sub/${token}/loon.conf`;
      configImportUrl = `loon://import?configuration=${encodeURIComponent(configUrl)}`;
    } else {
      subFile = "clash.yaml";
      subUrl = `https://${host}/sub/${token}/${subFile}`;
      importUrl = `clash://install-config?url=${encodeURIComponent(subUrl)}&name=o.o`;
    }

    const payload = {
      success: true,
      client: client || "clash",
      subscription_url: subUrl,
      import_url: importUrl
    };

    if (configUrl) {
      payload.config_url = configUrl;
      payload.config_import_url = configImportUrl;
    }

    return new Response(
      JSON.stringify(payload),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-store"
        }
      }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ success: false, error: "请求处理失败" }),
      {
        status: 500,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      }
    );
  }
}
