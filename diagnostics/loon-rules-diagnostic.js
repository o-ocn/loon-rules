/**
 * Loon Rules Diagnostic Script (Strategy-Neutral, Zero-Privacy, Safe Read-Only)
 * Target Environment: Loon Generic Script (iOS / iPadOS / macOS)
 * Author: o-ocn
 * License: GPL-2.0
 */

(function () {
  'use strict';

  // Config constants & base URLs (dynamic branch/ref support)
  let CURRENT_BRANCH = 'main';
  let PRIMARY_BASE_URL = 'https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist';
  let BACKUP_BASE_URL = 'https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist';
  let PRIMARY_MANIFEST_URL = PRIMARY_BASE_URL + '/diagnostics/manifest.json';
  let BACKUP_MANIFEST_URL = BACKUP_BASE_URL + '/diagnostics/manifest.json';

  function setBranch(branch) {
    if (!branch || typeof branch !== 'string') return;
    CURRENT_BRANCH = branch.trim();
    PRIMARY_BASE_URL = `https://raw.githubusercontent.com/o-ocn/loon-rules/${CURRENT_BRANCH}/dist`;
    BACKUP_BASE_URL = `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@${CURRENT_BRANCH}/dist`;
    PRIMARY_MANIFEST_URL = PRIMARY_BASE_URL + '/diagnostics/manifest.json';
    BACKUP_MANIFEST_URL = BACKUP_BASE_URL + '/diagnostics/manifest.json';
  }

  // Timeouts in milliseconds (Loon official unit for $httpClient is milliseconds)
  const PROBE_TIMEOUT_MS = 5000;
  const CONCURRENCY_LIMIT = 4;
  const USER_AGENT = 'Mozilla/5.0 LoonRulesDiagnostic/2.0';

  // Parse arguments
  function parseArgs() {
    let mode = 'quick';
    let branch = 'main';
    if (typeof $argument === 'string') {
      const parts = $argument.split('&');
      for (const p of parts) {
        const [k, v] = p.split('=');
        if (k && k.trim() === 'mode' && v) {
          mode = v.trim().toLowerCase();
        } else if (k && k.trim() === 'branch' && v) {
          branch = v.trim();
        }
      }
    }
    setBranch(branch);
    return { mode, branch };
  }

  // Pure JavaScript SHA-256 implementation (FIPS 180-4 compliant)
  // Runs in any JavaScript runtime without relying on crypto.subtle or Node.js require('crypto')
  function pureJsSha256(str) {
    function rotr(n, x) {
      return (x >>> n) | (x << (32 - n));
    }
    function ch(x, y, z) {
      return (x & y) ^ (~x & z);
    }
    function maj(x, y, z) {
      return (x & y) ^ (x & z) ^ (y & z);
    }
    function sigma0(x) {
      return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x);
    }
    function sigma1(x) {
      return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x);
    }
    function gamma0(x) {
      return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3);
    }
    function gamma1(x) {
      return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10);
    }

    // UTF-8 encoding
    const bytes = [];
    if (typeof TextEncoder !== 'undefined') {
      const u8 = new TextEncoder().encode(str);
      for (let i = 0; i < u8.length; i++) {
        bytes.push(u8[i]);
      }
    } else {
      for (let i = 0; i < str.length; i++) {
        let c = str.charCodeAt(i);
        if (c < 0x80) {
          bytes.push(c);
        } else if (c < 0x800) {
          bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
        } else if (c < 0xd800 || c >= 0xe000) {
          bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
        } else {
          i++;
          c = 0x10000 + (((c & 0x3ff) << 10) | (str.charCodeAt(i) & 0x3ff));
          bytes.push(
            0xf0 | (c >> 18),
            0x80 | ((c >> 12) & 0x3f),
            0x80 | ((c >> 6) & 0x3f),
            0x80 | (c & 0x3f)
          );
        }
      }
    }

    const bitLength = bytes.length * 8;
    bytes.push(0x80);
    while ((bytes.length % 64) !== 56) {
      bytes.push(0);
    }

    const highBits = Math.floor(bitLength / 0x100000000);
    const lowBits = (bitLength & 0xffffffff) >>> 0;
    bytes.push(
      (highBits >>> 24) & 0xff,
      (highBits >>> 16) & 0xff,
      (highBits >>> 8) & 0xff,
      highBits & 0xff,
      (lowBits >>> 24) & 0xff,
      (lowBits >>> 16) & 0xff,
      (lowBits >>> 8) & 0xff,
      lowBits & 0xff
    );

    const K = [
      0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];

    let H0 = 0x6a09e667, H1 = 0xbb67ae85, H2 = 0x3c6ef372, H3 = 0xa54ff53a;
    let H4 = 0x510e527f, H5 = 0x9b05688c, H6 = 0x1f83d9ab, H7 = 0x5be0cd19;

    const W = new Array(64);

    for (let i = 0; i < bytes.length; i += 64) {
      for (let t = 0; t < 16; t++) {
        const idx = i + t * 4;
        W[t] = ((bytes[idx] << 24) | (bytes[idx + 1] << 16) | (bytes[idx + 2] << 8) | bytes[idx + 3]) >>> 0;
      }
      for (let t = 16; t < 64; t++) {
        W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
      }

      let a = H0, b = H1, c = H2, d = H3, e = H4, f = H5, g = H6, h = H7;

      for (let t = 0; t < 64; t++) {
        const T1 = (h + sigma1(e) + ch(e, f, g) + K[t] + W[t]) >>> 0;
        const T2 = (sigma0(a) + maj(a, b, c)) >>> 0;
        h = g;
        g = f;
        f = e;
        e = (d + T1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (T1 + T2) >>> 0;
      }

      H0 = (H0 + a) >>> 0;
      H1 = (H1 + b) >>> 0;
      H2 = (H2 + c) >>> 0;
      H3 = (H3 + d) >>> 0;
      H4 = (H4 + e) >>> 0;
      H5 = (H5 + f) >>> 0;
      H6 = (H6 + g) >>> 0;
      H7 = (H7 + h) >>> 0;
    }

    function toHex(val) {
      return val.toString(16).padStart(8, '0');
    }

    return (toHex(H0) + toHex(H1) + toHex(H2) + toHex(H3) + toHex(H4) + toHex(H5) + toHex(H6) + toHex(H7)).toLowerCase();
  }

  // Safe SHA-256 calculation
  // Returns { ok: true, hash: string } or { ok: false, error: string }
  // Never returns null silently!
  function calculateSha256(text) {
    if (typeof text !== 'string') {
      return { ok: false, hash: null, error: '输入数据不是有效字符串' };
    }
    try {
      const hash = pureJsSha256(text);
      if (hash && hash.length === 64) {
        return { ok: true, hash, error: null };
      }
      return { ok: false, hash: null, error: 'SHA256 计算结果异常' };
    } catch (err) {
      return { ok: false, hash: null, error: '无法校验 SHA256 (计算环境异常)' };
    }
  }

  // HTTP helper wrapper around Loon's $httpClient
  // Strict Security:
  // - timeout in milliseconds (>= 1000)
  // - insecure: false (strictly verify TLS certificates)
  // - auto-cookie: false (strictly disable cookie persistence and reuse)
  function httpRequest(options, httpClientInstance) {
    const client = httpClientInstance || (typeof $httpClient !== 'undefined' ? $httpClient : null);
    if (!client) {
      return Promise.reject(new Error('Loon $httpClient not available'));
    }

    const opts = Object.assign({
      timeout: PROBE_TIMEOUT_MS,
      insecure: false,
      'auto-cookie': false,
      autoCookie: false,
      headers: { 'User-Agent': USER_AGENT }
    }, options);

    // Enforce millisecond timeout & strict security flags
    if (typeof opts.timeout !== 'number' || opts.timeout < 500) {
      opts.timeout = PROBE_TIMEOUT_MS;
    }
    opts.insecure = false;
    opts['auto-cookie'] = false;
    opts.autoCookie = false;

    return new Promise((resolve) => {
      const startTime = Date.now();
      const method = (opts.method || 'GET').toLowerCase();
      const fn = client[method] || client.get;

      fn.call(client, opts, (error, response, data) => {
        const duration = Date.now() - startTime;
        if (error) {
          resolve({
            ok: false,
            error: error.toString(),
            duration,
            status: 0,
            data: null
          });
        } else {
          resolve({
            ok: true,
            error: null,
            duration,
            status: response ? response.status : 0,
            headers: response ? response.headers : {},
            data
          });
        }
      });
    });
  }

  // Strictly maps all errors to safe, fixed categories (Zero raw string leaks)
  function classifyError(errStr) {
    if (!errStr) return '未知错误';
    const lower = String(errStr).toLowerCase();
    if (lower.includes('timeout') || lower.includes('timed out')) return '请求超时';
    if (lower.includes('dns') || lower.includes('resolve') || lower.includes('nodename') || lower.includes('enotfound') || lower.includes('getaddrinfo')) return 'DNS解析失败';
    if (lower.includes('tls') || lower.includes('ssl') || lower.includes('cert') || lower.includes('handshake')) return 'TLS握手错误';
    if (lower.includes('refused') || lower.includes('reset') || lower.includes('abort') || lower.includes('econnrefused')) return '连接被拒或重置';
    if (lower.includes('unreachable') || lower.includes('network is down') || lower.includes('enotconn')) return '网络不可达';
    if (lower.includes('http')) return 'HTTP错误';
    return '未知错误';
  }

  // Fetch and verify manifest from a given URL
  async function fetchManifestFromUrl(url, httpClient) {
    const res = await httpRequest({ url, timeout: PROBE_TIMEOUT_MS }, httpClient);
    if (res.ok && (res.status === 200 || res.status === 304) && res.data) {
      try {
        const manifest = JSON.parse(res.data);
        if (manifest && typeof manifest === 'object' && manifest.rulesets) {
          return { ok: true, manifest, duration: res.duration, error: null };
        }
      } catch (e) {}
      return { ok: false, manifest: null, duration: res.duration, error: 'manifest 数据解析失败' };
    }
    const errMsg = res.status
      ? (res.status === 404 ? 'HTTP 404 (资源不存在或尚未发布)' : `HTTP ${res.status}`)
      : classifyError(res.error);
    return { ok: false, manifest: null, duration: res.duration, error: errMsg };
  }

  // Inspect both primary and backup release bases
  // Compares package signature and per-ruleset hashes to verify both reachability AND version consistency
  async function checkReleaseSources(httpClient) {
    const [primaryRes, backupRes] = await Promise.all([
      fetchManifestFromUrl(PRIMARY_MANIFEST_URL, httpClient),
      fetchManifestFromUrl(BACKUP_MANIFEST_URL, httpClient)
    ]);

    let activeManifest = null;
    let sourceNote = '';
    let mirrorConsistent = false;

    if (primaryRes.ok && backupRes.ok) {
      activeManifest = primaryRes.manifest;
      const pMan = primaryRes.manifest;
      const bMan = backupRes.manifest;

      // Check package signature / release commit
      const pRev = pMan.content_revision || pMan.release_commit || '';
      const bRev = bMan.content_revision || bMan.release_commit || '';

      let hashMismatchCount = 0;
      if (pMan.rulesets && bMan.rulesets) {
        for (const [rname, pMeta] of Object.entries(pMan.rulesets)) {
          const bMeta = bMan.rulesets[rname];
          if (!bMeta || bMeta.sha256 !== pMeta.sha256 || bMeta.revision !== pMeta.revision) {
            hashMismatchCount++;
          }
        }
      }

      if (pRev === bRev && hashMismatchCount === 0) {
        mirrorConsistent = true;
        sourceNote = '主备双源均可达且内容同版本一致 (GitHub + jsDelivr)';
      } else {
        mirrorConsistent = false;
        sourceNote = `主备双源可达但版本不一致 (主版本: ${pRev || '未知'}, 备版本: ${bRev || '未知'}，差异规则集: ${hashMismatchCount} 项；镜像尚未同步)`;
      }
    } else if (primaryRes.ok) {
      activeManifest = primaryRes.manifest;
      sourceNote = 'GitHub 主源正常，jsDelivr 备用源不可达';
    } else if (backupRes.ok) {
      activeManifest = backupRes.manifest;
      sourceNote = 'GitHub 主源异常，已启用 jsDelivr 备用加速源';
    } else {
      sourceNote = `主备双源均不可达 (主: ${primaryRes.error}, 备: ${backupRes.error})`;
    }

    const primaryOk = Boolean(primaryRes.ok);
    const backupOk = Boolean(backupRes.ok);
    const isAllGood = Boolean(primaryOk && backupOk && mirrorConsistent);
    const hasWarning = Boolean(primaryOk && (!backupOk || !mirrorConsistent));
    const isDegraded = Boolean(!primaryOk && backupOk);

    return {
      primary: primaryRes,
      backup: backupRes,
      activeManifest,
      sourceNote,
      mirrorConsistent,
      primaryOk,
      backupOk,
      isAllGood,
      hasWarning,
      isDegraded,
      ok: Boolean(activeManifest)
    };
  }

  // Actually downloads and verifies a single .lsr ruleset file against manifest
  // Strictly checks:
  // 1. HTTP 200 and non-empty file
  // 2. # REVISION: header matches expected revision
  // 3. Separator presence and non-empty rule body
  // 4. Rule count matches expected total_rules
  // 5. SHA-256 of rule body matches expected sha256 (Never silently passes if hash unavailable)
  async function verifyRulesetFile(rulesetName, expectedMeta, baseUrl, httpClient) {
    const fileUrl = `${baseUrl}/${rulesetName}`;
    const res = await httpRequest({ url: fileUrl, timeout: PROBE_TIMEOUT_MS }, httpClient);

    if (!res.ok || res.status !== 200) {
      const errStr = res.status
        ? (res.status === 404 ? 'HTTP 404 (资源不存在或尚未发布)' : `HTTP ${res.status}`)
        : classifyError(res.error);
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: errStr
      };
    }

    const content = res.data || '';
    if (!content || content.length === 0) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: '文件内容为空 (0 bytes)'
      };
    }

    // Check # REVISION: header line
    const revMatch = content.match(/#\s*REVISION:\s*([a-f0-9]+)/i);
    const revision = revMatch ? revMatch[1].trim().toLowerCase() : '';
    if (!revision) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: '缺少 # REVISION 版本标识'
      };
    }

    // Assert revision match
    if (expectedMeta && expectedMeta.revision) {
      if (revision !== expectedMeta.revision.toLowerCase()) {
        return {
          ruleset: rulesetName,
          ok: false,
          duration: res.duration,
          error: `版本不匹配 (期望: ${expectedMeta.revision}, 实际: ${revision})`
        };
      }
    }

    // Check rule body separator (normalize CRLF to LF)
    const normalizedContent = content.replace(/\r\n/g, '\n');
    const sep = '# ==============================================================================\n';
    const parts = normalizedContent.split(sep);
    if (parts.length < 2) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: '缺少规则正文分隔符'
      };
    }

    const ruleBody = parts[1].replace(/\r\n/g, '\n').trim();
    if (!ruleBody || ruleBody.length === 0) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: '规则正文为空 (无有效规则条目)'
      };
    }

    // Count valid rule lines in body
    const bodyLines = ruleBody.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#') && !l.startsWith(';'));
    if (bodyLines.length === 0) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: '规则正文为空 (无有效规则行)'
      };
    }

    // Assert total_rules count
    if (expectedMeta && typeof expectedMeta.total_rules === 'number') {
      if (bodyLines.length !== expectedMeta.total_rules) {
        return {
          ruleset: rulesetName,
          ok: false,
          duration: res.duration,
          error: `规则条数不符 (期望: ${expectedMeta.total_rules}, 实际: ${bodyLines.length})`
        };
      }
    }

    // Strictly verify exact SHA-256 of rule body
    // If SHA calculation is not available or fails, it MUST fail and report '无法校验 SHA256'
    if (expectedMeta && expectedMeta.sha256) {
      const shaRes = calculateSha256(ruleBody);
      if (!shaRes.ok || !shaRes.hash) {
        return {
          ruleset: rulesetName,
          ok: false,
          duration: res.duration,
          error: shaRes.error || '无法校验 SHA256'
        };
      }
      if (shaRes.hash.toLowerCase() !== expectedMeta.sha256.toLowerCase()) {
        return {
          ruleset: rulesetName,
          ok: false,
          duration: res.duration,
          error: `SHA256 校验和不匹配 (期望: ${expectedMeta.sha256.slice(0, 8)}..., 实际: ${shaRes.hash.slice(0, 8)}...)`
        };
      }
    }

    return {
      ruleset: rulesetName,
      ok: true,
      duration: res.duration,
      revision,
      ruleCount: bodyLines.length,
      sizeBytes: content.length,
      error: null
    };
  }

  // Resolve active policy group for a service based on Loon runtime config
  // Prevents overseas AI services from defaulting to Hong Kong FINAL where AI endpoints are blocked
  function resolveTargetNode(service, loonConfig) {
    if (!loonConfig || !Array.isArray(loonConfig.all_policy_groups) || loonConfig.all_policy_groups.length === 0) {
      return null;
    }
    const allGroups = loonConfig.all_policy_groups;

    // 1. Direct match with service category (e.g. if user has a policy group named 'AI-Overseas')
    if (allGroups.includes(service.category)) {
      return service.category;
    }

    // 2. Specific matching for AI-Overseas services (avoid defaulting to Hong Kong FINAL where AI APIs are blocked)
    if (service.category === 'AI-Overseas') {
      const overseasCandidates = ['AI-Overseas', 'AI', 'All', 'US', 'Proxy', '全球节点', '节点选择'];
      for (const cand of overseasCandidates) {
        if (allGroups.includes(cand)) {
          return cand;
        }
      }
    }

    return null;
  }

  // Test single service endpoint on current route and DIRECT
  // Uses strictly neutral, factual observation
  async function testService(service, httpClient, targetNode = null) {
    const expected = service.expected_status || [200, 204];

    // Current route request (via Loon proxy / rule matching or resolved policy group)
    const routeReq = {
      url: service.url,
      method: service.method || 'GET',
      timeout: PROBE_TIMEOUT_MS
    };
    if (targetNode) {
      routeReq.node = targetNode;
    }
    const routeRes = await httpRequest(routeReq, httpClient);

    // DIRECT request (forced bypass)
    const directRes = await httpRequest({
      url: service.url,
      method: service.method || 'GET',
      node: 'DIRECT',
      timeout: PROBE_TIMEOUT_MS
    }, httpClient);

    const routeReachable = routeRes.ok && expected.includes(routeRes.status);
    const directReachable = directRes.ok && expected.includes(directRes.status);

    let isCaution = false;
    const cautionNotes = [];
    if ([401, 403, 404, 502].includes(routeRes.status)) {
      isCaution = true;
      cautionNotes.push(`HTTP ${routeRes.status}响应,应用功能未验证`);
    }
    if (service.id === 'apns_safe') {
      isCaution = true;
      cautionNotes.push('443探测响应,TCP5223与推送待实测');
    } else if (service.id === 'muse') {
      isCaution = true;
      cautionNotes.push('网站探针,不代表App功能');
    }

    const statusNote = cautionNotes.length > 0 ? ` [${cautionNotes.join('; ')}]` : '';
    const cautionNote = cautionNotes.join('; ');

    const routeDesc = targetNode ? `策略组[${targetNode}]` : '脚本默认路径';
    let verdict = '';
    let symbol = '✔';

    if (routeReachable && directReachable) {
      verdict = `当前路由可达 (${routeDesc}: ${routeRes.duration}ms) | DIRECT可达(${directRes.duration}ms) (双向均可达)${statusNote}`;
    } else if (routeReachable && !directReachable) {
      verdict = `当前路由可达 (${routeDesc}: ${routeRes.duration}ms) | DIRECT不可达 (仅当前路由可达, DIRECT不可达)${statusNote}`;
    } else if (!routeReachable && directReachable) {
      symbol = '✘';
      const errName = routeRes.status ? `HTTP ${routeRes.status}` : classifyError(routeRes.error);
      verdict = `当前路由不可达(${errName}) | DIRECT可达 (仅DIRECT可达, 当前路由不可达)`;
    } else {
      symbol = '⚠';
      const rErr = routeRes.status ? `HTTP ${routeRes.status}` : classifyError(routeRes.error);
      const dErr = directRes.status ? `HTTP ${directRes.status}` : classifyError(directRes.error);
      verdict = `当前路由与DIRECT均不可达 (路由: ${rErr}, DIRECT: ${dErr}；双向均不可达)`;
    }

    return {
      id: service.id,
      name: service.name,
      category: service.category,
      symbol,
      routeReachable,
      directReachable,
      routeDuration: routeRes.duration,
      directDuration: directRes.duration,
      status: routeRes.status,
      targetNode,
      isCaution,
      cautionNote,
      verdict
    };
  }

  // Controlled concurrency batch runner with cancellation and item completion callback
  async function mapConcurrent(items, limit, fn, shouldStop, onItemCompleted) {
    const results = [];
    let index = 0;

    async function worker() {
      while (index < items.length) {
        if (shouldStop && shouldStop()) {
          break;
        }
        const currentIndex = index++;
        const res = await fn(items[currentIndex]);
        results[currentIndex] = res;
        if (onItemCompleted) {
          try {
            onItemCompleted(items[currentIndex], res);
          } catch (e) {}
        }
      }
    }

    const workers = [];
    const count = Math.min(limit, items.length);
    for (let i = 0; i < count; i++) {
      workers.push(worker());
    }
    await Promise.all(workers);
    return results;
  }

  // Live diagnostic execution progress tracker for safe watchdog reporting
  const currentProgress = {
    mode: 'quick',
    startTime: 0,
    sourcesStatus: null,
    manifest: null,
    rulesetVerifiedCount: 0,
    rulesetTotalToTest: 0,
    rulesetFailed: [],
    completedServices: [],
    countBothPass: 0,
    countProxyOnly: 0,
    countDirectOnly: 0,
    countBothFail: 0,
    totalServices: 0,
    reset: function(mode) {
      this.mode = mode || 'quick';
      this.startTime = Date.now();
      this.sourcesStatus = null;
      this.manifest = null;
      this.rulesetVerifiedCount = 0;
      this.rulesetTotalToTest = 0;
      this.rulesetFailed = [];
      this.completedServices = [];
      this.countBothPass = 0;
      this.countProxyOnly = 0;
      this.countDirectOnly = 0;
      this.countBothFail = 0;
      this.totalServices = 0;
    },
    formatPartialReport: function(reason) {
      const modeStr = this.mode === 'full' ? '完整诊断' : '快速诊断';
      const timeoutLimit = this.mode === 'full' ? '56s' : '27s';
      const lines = [
        '【Loon 规则与连通性诊断报告】',
        `- 模式: ${modeStr} [${reason || '时限保护 - 部分报告'}]`,
        `- 状态: 运行达到安全时限 (${timeoutLimit})，在途网络请求未被底层 API 中断，但报告生成已截止。`
      ];

      if (this.manifest && this.manifest.content_revision) {
        lines.push(`- 版本标识: ${this.manifest.content_revision}`);
      }

      if (this.sourcesStatus) {
        lines.push(`- 发布源状态: ${this.sourcesStatus.sourceNote || '已检测'}`);
      }

      if (this.rulesetTotalToTest > 0) {
        lines.push(`- 规则集进度: 已验证 ${this.rulesetVerifiedCount}/${this.rulesetTotalToTest} 个 (失败: ${this.rulesetFailed.length})`);
      }

      if (this.completedServices.length > 0) {
        lines.push(`- 已完成服务探测: ${this.completedServices.length}/${this.totalServices || this.completedServices.length} 项 (其中 ${this.countProxyOnly} 项仅当前路由可达, DIRECT不可达, ${this.countBothPass} 项双向均可达)`);
        lines.push('- 部分连通性分布:');
        for (const s of this.completedServices) {
          lines.push(`  * ${s.name}: ${s.statusDesc}`);
        }
        lines.push(`- 结论: 服务探测未完成 (${this.completedServices.length}/${this.totalServices || this.completedServices.length})，已完成结果仅供参考。`);
      } else {
        lines.push('- 服务探测: 超时前未能完成任何服务探测。');
        lines.push('- 结论: 超时，未形成结论。请检查网络或切换节点后重试。');
      }

      lines.push('----------------------------------------');
      lines.push('【能力边界提示 (需真机验证)】仅探测已知 HTTPS 端点，无法自动发现全部未知域名。若遇稳定异常，应先核对上游更新与规则；仅在仍无法定位时，方需提供一次本地脱敏请求记录。本插件不能探测 APNs TCP 5223，亦不能替代 Telegram 锁屏蜂窝推送、HomeKit 摄像头、Apple Watch 及 CloudKit 真机测试。');
      return lines.join('\n');
    }
  };

  // Main diagnostic execution
  async function runDiagnostic(options = {}) {
    const httpClient = options.httpClient || (typeof $httpClient !== 'undefined' ? $httpClient : null);
    const mode = options.mode || parseArgs().mode;
    const startTime = Date.now();
    const deadlineMs = options.deadlineMs || ((mode === 'full') ? 52000 : 25000);

    // Retrieve active policy groups from Loon configuration if available
    let loonConfig = (options && options.config) || null;
    if (!loonConfig && typeof $config !== 'undefined' && typeof $config.getConfig === 'function') {
      try {
        const confRaw = $config.getConfig();
        loonConfig = typeof confRaw === 'string' ? JSON.parse(confRaw) : confRaw;
      } catch (e) {}
    }

    currentProgress.reset(mode);

    function isDeadlineExceeded() {
      return (Date.now() - startTime) >= deadlineMs;
    }

    const reportLines = [];
    reportLines.push('【Loon 规则与核心服务诊断报告】');
    reportLines.push(`诊断模式: ${mode === 'full' ? '完整诊断 (全量规则校验与服务)' : '快速诊断 (核心规则与服务)'} | 生成时间: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC`);
    reportLines.push('----------------------------------------');

    // 1. Check Primary and Backup Release Sources & Manifest (Concurrent)
    const sourcesStatus = await checkReleaseSources(httpClient);
    currentProgress.sourcesStatus = sourcesStatus;
    const manifest = sourcesStatus.activeManifest;
    currentProgress.manifest = manifest;
    const repoOk = sourcesStatus.ok;

    if (sourcesStatus.isAllGood && manifest) {
      reportLines.push(`[✓] 发布源状态: ${sourcesStatus.sourceNote}`);
      const rsetCount = manifest.rulesets ? Object.keys(manifest.rulesets).length : 0;
      reportLines.push(`- 版本标识: ${manifest.content_revision || '最新'} (构建时间: ${manifest.build_timestamp || '未知'}, 清单: ${rsetCount} 个规则集)`);
    } else if (sourcesStatus.hasWarning && manifest) {
      reportLines.push(`[!] 发布源状态 (警告): ${sourcesStatus.sourceNote}`);
      const rsetCount = manifest.rulesets ? Object.keys(manifest.rulesets).length : 0;
      reportLines.push(`- 版本标识: ${manifest.content_revision || '最新'} (构建时间: ${manifest.build_timestamp || '未知'}, 清单: ${rsetCount} 个规则集)`);
    } else if (sourcesStatus.isDegraded && manifest) {
      reportLines.push(`[!] 发布源状态 (降级): ${sourcesStatus.sourceNote}`);
      const rsetCount = manifest.rulesets ? Object.keys(manifest.rulesets).length : 0;
      reportLines.push(`- 版本标识: ${manifest.content_revision || '最新'} (构建时间: ${manifest.build_timestamp || '未知'}, 清单: ${rsetCount} 个规则集)`);
    } else {
      reportLines.push(`[✘] 规则发布源不可达: ${sourcesStatus.sourceNote}`);
      reportLines.push('  判断: 规则资源下载受阻，请检查网络连接或切换备用镜像');
    }

    reportLines.push('----------------------------------------');

    // 2. Download and verify actual .lsr ruleset files (Concurrent)
    let rulesetFailure = false;
    let rulesetIncomplete = false;
    let timedOut = false;
    const failedRulesets = [];
    let verifiedCount = 0;
    let toTestLength = 0;

    if (repoOk && manifest && manifest.rulesets) {
      const activeBase = sourcesStatus.primary.ok ? PRIMARY_BASE_URL : BACKUP_BASE_URL;
      const allRulesets = Object.keys(manifest.rulesets);
      const toTest = mode === 'full'
        ? allRulesets
        : allRulesets.filter(r => ['AI-Overseas.lsr', 'Apple-Push.lsr', 'GoogleDrive.lsr', 'China-Direct.lsr'].includes(r));
      toTestLength = toTest.length;
      currentProgress.rulesetTotalToTest = toTestLength;

      const vResults = await mapConcurrent(toTest, CONCURRENCY_LIMIT, async (rname) => {
        const meta = manifest.rulesets[rname];
        return await verifyRulesetFile(rname, meta, activeBase, httpClient);
      }, isDeadlineExceeded, (rname, res) => {
        if (res && res.ok) {
          currentProgress.rulesetVerifiedCount++;
        } else if (res) {
          currentProgress.rulesetFailed.push(res);
        }
      });

      for (let i = 0; i < vResults.length; i++) {
        const vRes = vResults[i];
        if (!vRes) continue; // skipped due to timeout
        if (vRes.ok) {
          verifiedCount++;
        } else {
          rulesetFailure = true;
          failedRulesets.push(vRes);
        }
      }

      if (isDeadlineExceeded()) {
        timedOut = true;
      }

      if (failedRulesets.length === 0 && verifiedCount === toTestLength) {
        const sampleRev = manifest.rulesets[toTest[0]]?.revision || '一致';
        reportLines.push(`[✓] 规则集校验: 全部 ${toTestLength} 个规则集正文、条数与 SHA256 均校验通过 (版本: ${sampleRev})`);
      } else {
        if (failedRulesets.length > 0) {
          for (const f of failedRulesets) {
            reportLines.push(`[✘] ${f.ruleset}: 校验失败 (${f.error})`);
          }
        }
        if (verifiedCount < toTestLength) {
          rulesetIncomplete = true;
          reportLines.push(`[!] 规则集校验: 未完成 (已验证 ${verifiedCount}/${toTestLength} 个规则集，部分项因时限跳过)`);
        }
      }

      // In full mode: verify ALL rulesets from backup source (jsDelivr)
      if (mode === 'full' && sourcesStatus.backup.ok) {
        if (isDeadlineExceeded()) {
          rulesetIncomplete = true;
          reportLines.push('[!] 备用源规则集: 未完成 (因时限跳过)');
        } else {
          const failedBackupRulesets = [];
          let backupVerifiedCount = 0;

          const bResults = await mapConcurrent(allRulesets, CONCURRENCY_LIMIT, async (rname) => {
            const bMeta = manifest.rulesets[rname];
            return await verifyRulesetFile(rname, bMeta, BACKUP_BASE_URL, httpClient);
          }, isDeadlineExceeded, (rname, res) => {
            if (res && !res.ok) {
              currentProgress.rulesetFailed.push(res);
            }
          });

          for (let i = 0; i < bResults.length; i++) {
            const bRes = bResults[i];
            if (!bRes) continue;
            if (bRes.ok) {
              backupVerifiedCount++;
            } else {
              rulesetFailure = true; // Backup failure triggers rulesetFailure
              failedBackupRulesets.push(bRes);
            }
          }

          if (failedBackupRulesets.length === 0 && backupVerifiedCount === allRulesets.length) {
            reportLines.push(`[✓] 备用源规则集: 全部 ${allRulesets.length} 个规则集 jsDelivr 镜像正文与 SHA256 均校验通过`);
          } else {
            if (failedBackupRulesets.length > 0) {
              for (const f of failedBackupRulesets) {
                reportLines.push(`[✘] 备用源: ${f.ruleset} 校验失败 (${f.error})`);
              }
            }
            if (backupVerifiedCount < allRulesets.length) {
              rulesetIncomplete = true;
              reportLines.push(`[!] 备用源规则集: 未完成 (已验证 ${backupVerifiedCount}/${allRulesets.length} 个规则集，部分项因时限跳过)`);
            }
          }
        }
      }
    } else {
      reportLines.push('[!] 规则正文校验: 未执行 (主备清单均不可用)');
    }

    reportLines.push('----------------------------------------');

    // 3. Select Services to Test (Concurrent)
    let serviceList = [];
    if (manifest && Array.isArray(manifest.services) && manifest.services.length > 0) {
      serviceList = manifest.services;
    } else {
      serviceList = [
        { id: 'chatgpt', name: 'ChatGPT / OpenAI', url: 'https://chatgpt.com/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
        { id: 'gemini', name: 'Google Gemini', url: 'https://gemini.google.com/', expected_status: [200, 301, 302, 400, 404], quick: true },
        { id: 'claude', name: 'Claude / Anthropic', url: 'https://claude.ai/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
        { id: 'deepseek', name: 'DeepSeek (大陆 AI)', url: 'https://api.deepseek.com/', expected_status: [200, 401, 404], quick: true },
        { id: 'googledrive', name: 'Google Drive', url: 'https://drive.google.com/drive/my-drive', expected_status: [200, 301, 302], quick: true },
        { id: 'google', name: 'Google 通用服务', url: 'https://www.google.com/generate_204', expected_status: [204, 200], quick: true },
        { id: 'youtube', name: 'YouTube 流媒体', url: 'https://www.youtube.com/generate_204', expected_status: [204, 200], quick: true },
        { id: 'telegram', name: 'Telegram 平台', url: 'https://t.me/telegram', expected_status: [200, 301, 302], quick: true },
        { id: 'github', name: 'GitHub 规则源', url: 'https://github.com/robots.txt', expected_status: [200, 301, 302], quick: true },
        { id: 'icloud', name: 'Apple iCloud', url: 'https://www.icloud.com/', expected_status: [200, 301, 302], quick: true },
        { id: 'grok', name: 'xAI / Grok', url: 'https://grok.com/', expected_status: [200, 301, 302, 401, 403, 404], quick: false },
        { id: 'muse', name: 'Muse from Meta', url: 'https://muse.ai/', expected_status: [200, 301, 302], quick: false },
        { id: 'testflight', name: 'Apple TestFlight', url: 'https://testflight.apple.com/v1/session', expected_status: [200, 401, 403, 404], quick: false },
        { id: 'apns_safe', name: 'Apple APNs (HTTPS安全测试)', url: 'https://courier.push.apple.com/', expected_status: [200, 400, 403, 404, 502], quick: false }
      ];
    }

    if (mode === 'quick') {
      serviceList = serviceList.filter(s => s.quick === true);
    }

    currentProgress.totalServices = serviceList.length;

    let countBothPass = 0;
    let countProxyOnly = 0;
    let countDirectOnly = 0;
    let countBothFail = 0;
    const abnormalServices = [];
    let totalTested = 0;

    const sResults = await mapConcurrent(serviceList, CONCURRENCY_LIMIT, async (s) => {
      const targetNode = resolveTargetNode(s, loonConfig);
      return await testService(s, httpClient, targetNode);
    }, isDeadlineExceeded, (s, res) => {
      if (!res) return;
      let statusDesc = '';
      if (res.routeReachable && res.directReachable) {
        currentProgress.countBothPass++;
        statusDesc = '可达 (双向均可达)';
      } else if (res.routeReachable && !res.directReachable) {
        currentProgress.countProxyOnly++;
        statusDesc = '可达 (仅当前路由可达, DIRECT不可达)';
      } else if (!res.routeReachable && res.directReachable) {
        currentProgress.countDirectOnly++;
        statusDesc = '异常 (仅DIRECT可达, 当前路由不可达)';
      } else {
        currentProgress.countBothFail++;
        statusDesc = '不可达 (双向均不可达)';
      }
      currentProgress.completedServices.push({
        id: s.id,
        name: s.name,
        statusDesc: statusDesc
      });
    });

    if (isDeadlineExceeded()) {
      timedOut = true;
    }

    const cautionServices = [];
    for (let i = 0; i < sResults.length; i++) {
      const res = sResults[i];
      if (!res) continue;
      totalTested++;
      if (res.isCaution && (res.routeReachable || res.directReachable)) {
        cautionServices.push(res);
      }
      if (res.routeReachable && res.directReachable) {
        countBothPass++;
      } else if (res.routeReachable && !res.directReachable) {
        countProxyOnly++;
      } else if (!res.routeReachable && res.directReachable) {
        countDirectOnly++;
        abnormalServices.push({ ...res, category: 'direct_only' });
      } else {
        countBothFail++;
        abnormalServices.push({ ...res, category: 'both_fail' });
      }
    }

    const hasRouteFailure = (countDirectOnly > 0 || countBothFail > 0);
    const hasRouteBlockedWhileDirectOk = (countDirectOnly > 0);

    const serviceIncomplete = (totalTested < serviceList.length);

    if (abnormalServices.length === 0 && !serviceIncomplete) {
      if (countProxyOnly > 0) {
        reportLines.push(`[✓] 服务连通性: 共探测 ${totalTested} 项服务，当前路由均可达 (其中 ${countProxyOnly} 项仅当前路由可达, DIRECT不可达, ${countBothPass} 项双向均可达)`);
      } else {
        reportLines.push(`[✓] 服务连通性: 全部 ${totalTested} 项服务当前路由与 DIRECT 均可达 (双向均可达)`);
      }
      if (cautionServices.length > 0) {
        reportLines.push(`- 端点有响应但应用功能待真机验证 (共 ${cautionServices.length} 项):`);
        for (const cs of cautionServices) {
          reportLines.push(`  * ${cs.name}: ${cs.cautionNote}`);
        }
      }
    } else if (abnormalServices.length === 0 && serviceIncomplete) {
      reportLines.push(`[!] 服务连通性: 未完成 (已探测 ${totalTested}/${serviceList.length} 项服务，当前路由均可达；部分项因时限跳过)`);
      reportLines.push(`- 连通性分布: 其中 ${countProxyOnly} 项仅当前路由可达, DIRECT不可达, ${countBothPass} 项双向均可达`);
      if (cautionServices.length > 0) {
        reportLines.push(`- 端点有响应但应用功能待真机验证 (共 ${cautionServices.length} 项):`);
        for (const cs of cautionServices) {
          reportLines.push(`  * ${cs.name}: ${cs.cautionNote}`);
        }
      }
    } else {
      reportLines.push(`[!] 服务连通性: 探测 ${totalTested} 项服务中发现 ${abnormalServices.length} 项异常 (仅当前路由可达: ${countProxyOnly}, 双向均可达: ${countBothPass})`);
      for (const res of abnormalServices) {
        if (res.category === 'direct_only') {
          reportLines.push(`  ✘ ${res.name}: 仅 DIRECT 可达 | 当前路由不可达 (建议检查该服务命中规则、策略组或出口节点)`);
        } else {
          reportLines.push(`  ⚠ ${res.name}: 当前路由与 DIRECT 均不可达 (可能网络中断、端点不可达或服务宕机)`);
        }
      }
      if (cautionServices.length > 0) {
        reportLines.push(`- 端点有响应但应用功能待真机验证 (共 ${cautionServices.length} 项):`);
        for (const cs of cautionServices) {
          reportLines.push(`  * ${cs.name}: ${cs.cautionNote}`);
        }
      }
      if (serviceIncomplete) {
        reportLines.push(`- 连通性进度: 已完成 ${totalTested}/${serviceList.length} 项探测 (部分项因时限跳过)`);
      }
    }

    reportLines.push('----------------------------------------');

    // 4. Comprehensive Conclusion
    const durationTotal = ((Date.now() - startTime) / 1000).toFixed(1);

    if (!repoOk) {
      reportLines.push('❗ 诊断结论: 规则发布源清单无法下载或损坏，规则正文校验未执行，请检查网络或切换备用镜像');
    } else if (rulesetFailure) {
      reportLines.push('⚠️ 诊断结论: 部分 .lsr 规则集文件下载失败或哈希校验不匹配，请刷新规则订阅');
    } else if (rulesetIncomplete) {
      reportLines.push('⚠️ 诊断结论: 规则集校验因时限未完全完成，已完成部分有效；请在网络良好时重试完整校验');
    } else if (countDirectOnly > 0 && countBothFail === 0) {
      reportLines.push(`⚠️ 诊断结论: 发现 ${countDirectOnly} 项服务仅 DIRECT 可达但当前路由不可达，建议在 Loon 中检查该服务命中规则、绑定策略组或出口节点`);
    } else if (countBothFail > 0) {
      reportLines.push(`⚠️ 诊断结论: 发现 ${countBothFail} 项服务两者均不可达，可能为目标服务临时宕机或本地网络受限`);
    } else if (serviceIncomplete) {
      reportLines.push(`⚠️ 诊断结论: 服务探测未完成 (${totalTested}/${serviceList.length})，已完成结果仅供参考；请在网络良好时重试完整探测。 (耗时: ${durationTotal}s)`);
    } else if (sourcesStatus.hasWarning) {
      reportLines.push(`⚠️ 诊断结论: 已检测核心服务连通性均正常，但发布源存在警告 (${sourcesStatus.sourceNote})；提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。 (耗时: ${durationTotal}s)`);
    } else if (sourcesStatus.isDegraded) {
      reportLines.push(`⚠️ 诊断结论: 已检测核心服务连通性均正常，但发布源处于降级状态 (${sourcesStatus.sourceNote})；提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。 (耗时: ${durationTotal}s)`);
    } else if (countProxyOnly > 0) {
      const tipNote = cautionServices.length > 0
        ? `提示: 其中 ${cautionServices.length} 项仅为端点探测响应，应用功能与推送待真机实测。`
        : `提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。`;
      reportLines.push(`✔ 诊断结论: 已检测核心服务连通性均正常 (${countProxyOnly} 项仅当前路由可达/DIRECT不可达, ${countBothPass} 项双向均可达)；${tipNote} (耗时: ${durationTotal}s)`);
    } else {
      const tipNote = cautionServices.length > 0
        ? `提示: 其中 ${cautionServices.length} 项仅为端点探测响应，应用功能与推送待真机实测。`
        : `提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。`;
      reportLines.push(`✔ 诊断结论: 已检测核心服务连通性均正常 (双向均可达)；${tipNote} (耗时: ${durationTotal}s)`);
    }

    if (timedOut) {
      reportLines.push('⚠️ 提示: 检测耗时接近限额，已安全产出部分诊断报告以避免被系统强制中止');
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【能力边界提示 (需真机验证)】仅探测已知 HTTPS 端点，无法自动发现全部未知域名。若遇稳定异常，应先核对上游更新与规则；仅在仍无法定位时，方需提供一次本地脱敏请求记录。本插件不能探测 APNs TCP 5223，亦不能替代 Telegram 锁屏蜂窝推送、HomeKit 摄像头、Apple Watch 及 CloudKit 真机测试。');
    reportLines.push('========================================');

    const finalReport = reportLines.join('\n');
    return {
      report: finalReport,
      repoOk,
      rulesetFailure,
      rulesetIncomplete,
      serviceIncomplete,
      sourcesStatus,
      hasWarning: Boolean(sourcesStatus && sourcesStatus.hasWarning),
      isDegraded: Boolean(sourcesStatus && sourcesStatus.isDegraded),
      hasRouteFailure,
      hasRouteBlockedWhileDirectOk,
      countBothPass,
      countProxyOnly,
      countDirectOnly,
      countBothFail,
      totalTested,
      totalServices: serviceList.length,
      timedOut,
      duration: durationTotal
    };
  }

  // Loon Execution Entrypoint with Safe Single-$done Guard and Watchdog
  function initLoonEntrypoint(env = {}) {
    const doneFn = env.$done || (typeof $done !== 'undefined' ? $done : null);
    if (!doneFn) return null;

    let doneCalled = false;
    function safeDone(payload) {
      if (doneCalled) return;
      doneCalled = true;
      doneFn(payload);
    }

    const setTimer = env.setTimeout || setTimeout;
    const clearTimer = env.clearTimeout || clearTimeout;
    const args = env.args || parseArgs();
    const isFull = (args.mode === 'full');
    const watchdogTimeoutMs = isFull ? 56000 : 27000;

    // Safety watchdog to guarantee $done before Loon aborts
    const watchdogTimer = setTimer(() => {
      const partialReport = currentProgress.formatPartialReport('时限保护 - 部分报告');
      safeDone({
        title: `Loon 规则诊断 (${isFull ? '完整' : '快速'}模式超时)`,
        content: partialReport
      });
    }, watchdogTimeoutMs);

    runDiagnostic({ mode: args.mode, httpClient: env.$httpClient, deadlineMs: env.deadlineMs }).then((res) => {
      clearTimer(watchdogTimer);
      console.log(res.report);
      const notifFn = env.$notification || (typeof $notification !== 'undefined' ? $notification : null);
      if (notifFn) {
        let title = '';
        let subtitle = '';

        if (res.hasRouteFailure || res.rulesetFailure || !res.repoOk) {
          title = 'Loon 规则诊断: 发现异常';
        } else if (res.hasWarning || res.isDegraded || res.rulesetIncomplete || res.serviceIncomplete) {
          title = 'Loon 规则诊断: 存在警告';
        } else {
          title = 'Loon 规则诊断: 连通性正常';
        }

        if (res.hasRouteBlockedWhileDirectOk) {
          subtitle = '存在路由不可达但 DIRECT 可达项 (仅DIRECT可达)';
        } else if (res.rulesetFailure) {
          subtitle = '规则集校验失败，点击查看报告';
        } else if (res.rulesetIncomplete) {
          subtitle = '规则集校验未完全完成，点击查看报告';
        } else if (res.serviceIncomplete) {
          subtitle = `服务探测未完成 (${res.totalTested}/${res.totalServices})，已完成结果仅供参考`;
        } else if (res.hasWarning) {
          subtitle = '发布源存在警告或镜像未同步，点击查看报告';
        } else if (res.isDegraded) {
          subtitle = '发布源处于降级状态，点击查看报告';
        } else {
          subtitle = `已检测 ${res.totalTested} 项服务均可达 (${res.duration}s)，点击查看报告`;
        }

        notifFn.post(title, subtitle, '已输出至 Loon 日志，可直接全选复制反馈');
      }
      safeDone({
        title: 'Loon 规则诊断',
        content: res.report
      });
    }).catch((err) => {
      clearTimer(watchdogTimer);
      console.log('Diagnostic error occurred');
      const notifFn = env.$notification || (typeof $notification !== 'undefined' ? $notification : null);
      if (notifFn) {
        notifFn.post('Loon 规则诊断失败', '执行异常', classifyError(err));
      }
      safeDone({ error: classifyError(err) });
    });

    return { safeDone, watchdogTimer };
  }

  // Automatic execution if running inside Loon runtime
  if (typeof $done !== 'undefined') {
    initLoonEntrypoint();
  }

  // Export for automated local testing
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      runDiagnostic,
      testService,
      resolveTargetNode,
      fetchManifestFromUrl,
      checkReleaseSources,
      verifyRulesetFile,
      classifyError,
      calculateSha256,
      pureJsSha256,
      mapConcurrent,
      currentProgress,
      initLoonEntrypoint,
      setBranch,
      get PRIMARY_BASE_URL() { return PRIMARY_BASE_URL; },
      get BACKUP_BASE_URL() { return BACKUP_BASE_URL; },
      get PRIMARY_MANIFEST_URL() { return PRIMARY_MANIFEST_URL; },
      get BACKUP_MANIFEST_URL() { return BACKUP_MANIFEST_URL; },
      PROBE_TIMEOUT_MS,
      CONCURRENCY_LIMIT
    };
  }
})();
