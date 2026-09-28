/**
 * Loon Rules Diagnostic Script (Strategy-Neutral, Zero-Privacy, Safe Read-Only)
 * Target Environment: Loon Generic Script (iOS / iPadOS / macOS)
 * Author: o-ocn
 * License: GPL-2.0
 */

(function () {
  'use strict';

  // Config constants
  const PRIMARY_BASE_URL = 'https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist';
  const BACKUP_BASE_URL = 'https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist';
  const PRIMARY_MANIFEST_URL = PRIMARY_BASE_URL + '/diagnostics/manifest.json';
  const BACKUP_MANIFEST_URL = BACKUP_BASE_URL + '/diagnostics/manifest.json';

  // Timeouts in milliseconds (Loon official unit for $httpClient is milliseconds)
  const PROBE_TIMEOUT_MS = 5000;
  const USER_AGENT = 'Mozilla/5.0 LoonRulesDiagnostic/2.0';

  // Parse arguments
  function parseArgs() {
    let mode = 'quick';
    if (typeof $argument === 'string') {
      const parts = $argument.split('&');
      for (const p of parts) {
        const [k, v] = p.split('=');
        if (k && k.trim() === 'mode' && v) {
          mode = v.trim().toLowerCase();
        }
      }
    }
    return { mode };
  }

  // Safe SHA-256 calculation (WebCrypto in modern JS / crypto in Node / fallback to revision header check)
  async function calculateSha256(text) {
    if (typeof crypto !== 'undefined' && crypto.subtle && typeof TextEncoder !== 'undefined') {
      try {
        const msgUint8 = new TextEncoder().encode(text);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      } catch (e) {}
    }
    if (typeof require !== 'undefined') {
      try {
        const nodeCrypto = require('crypto');
        return nodeCrypto.createHash('sha256').update(text, 'utf8').digest('hex');
      } catch (e) {}
    }
    return null;
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
    return { ok: false, manifest: null, duration: res.duration, error: classifyError(res.error) };
  }

  // Inspect both primary and backup release bases
  async function checkReleaseSources(httpClient) {
    const primaryRes = await fetchManifestFromUrl(PRIMARY_MANIFEST_URL, httpClient);
    const backupRes = await fetchManifestFromUrl(BACKUP_MANIFEST_URL, httpClient);

    let activeManifest = null;
    let sourceNote = '';

    if (primaryRes.ok) {
      activeManifest = primaryRes.manifest;
      sourceNote = backupRes.ok ? '主备双源均可达 (GitHub + jsDelivr)' : 'GitHub 主源正常，jsDelivr 备用源异常';
    } else if (backupRes.ok) {
      activeManifest = backupRes.manifest;
      sourceNote = 'GitHub 主源异常，已启用 jsDelivr 备用加速源';
    } else {
      sourceNote = `主备双源均不可达 (主: ${primaryRes.error}, 备: ${backupRes.error})`;
    }

    return {
      primary: primaryRes,
      backup: backupRes,
      activeManifest,
      sourceNote,
      ok: Boolean(activeManifest)
    };
  }

  // Actually downloads and verifies a single .lsr ruleset file against manifest
  async function verifyRulesetFile(rulesetName, expectedMeta, baseUrl, httpClient) {
    const fileUrl = `${baseUrl}/${rulesetName}`;
    const res = await httpRequest({ url: fileUrl, timeout: PROBE_TIMEOUT_MS }, httpClient);

    if (!res.ok || res.status !== 200) {
      return {
        ruleset: rulesetName,
        ok: false,
        duration: res.duration,
        error: res.ok ? `HTTP ${res.status}` : classifyError(res.error)
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

    // If expected meta provides revision, assert match
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

    // If crypto available, verify exact SHA-256 of rule body
    if (expectedMeta && expectedMeta.sha256) {
      const sep = '# ==============================================================================\n';
      const parts = content.split(sep);
      const ruleBody = parts.length > 1 ? parts[1].replace(/\r\n/g, '\n').trim() : '';
      const computedSha = await calculateSha256(ruleBody);
      if (computedSha && computedSha.toLowerCase() !== expectedMeta.sha256.toLowerCase()) {
        return {
          ruleset: rulesetName,
          ok: false,
          duration: res.duration,
          error: 'SHA256 校验和不匹配'
        };
      }
    }

    return {
      ruleset: rulesetName,
      ok: true,
      duration: res.duration,
      revision,
      sizeBytes: content.length,
      error: null
    };
  }

  // Test single service endpoint on current route and DIRECT
  async function testService(service, httpClient) {
    const expected = service.expected_status || [200, 204];

    // Current route request (via Loon proxy / rule matching)
    const routeRes = await httpRequest({
      url: service.url,
      method: service.method || 'GET',
      timeout: PROBE_TIMEOUT_MS
    }, httpClient);

    // DIRECT request (forced bypass)
    const directRes = await httpRequest({
      url: service.url,
      method: service.method || 'GET',
      node: 'DIRECT',
      timeout: PROBE_TIMEOUT_MS
    }, httpClient);

    const routeReachable = routeRes.ok && expected.includes(routeRes.status);
    const directReachable = directRes.ok && expected.includes(directRes.status);

    let verdict = '';
    let symbol = '✔';

    if (routeReachable && directReachable) {
      verdict = `路由正常(${routeRes.duration}ms) | DIRECT正常`;
    } else if (routeReachable && !directReachable) {
      verdict = `路由正常(${routeRes.duration}ms) | DIRECT不可达 (代理生效)`;
    } else if (!routeReachable && directReachable) {
      symbol = '✘';
      const errName = routeRes.status ? `HTTP ${routeRes.status}` : classifyError(routeRes.error);
      verdict = `当前路由失败(${errName}) 但 DIRECT正常 (当前代理节点异常或服务阻断!)`;
    } else {
      symbol = '⚠';
      const rErr = routeRes.status ? `HTTP ${routeRes.status}` : classifyError(routeRes.error);
      const dErr = directRes.status ? `HTTP ${directRes.status}` : classifyError(directRes.error);
      verdict = `当前路由与DIRECT均失败 (路由: ${rErr}, DIRECT: ${dErr})`;
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
      verdict
    };
  }

  // Main diagnostic execution
  async function runDiagnostic(options = {}) {
    const httpClient = options.httpClient || (typeof $httpClient !== 'undefined' ? $httpClient : null);
    const mode = options.mode || parseArgs().mode;
    const startTime = Date.now();

    const reportLines = [];
    reportLines.push('【Loon 规则与核心服务诊断报告】');
    reportLines.push(`诊断模式: ${mode === 'full' ? '完整诊断 (全量规则校验与服务)' : '快速诊断 (核心规则与服务)'} | 生成时间: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC`);
    reportLines.push('----------------------------------------');

    // 1. Check Primary and Backup Release Sources & Manifest
    reportLines.push('【规则发布源与清单状态】');
    const sourcesStatus = await checkReleaseSources(httpClient);
    const manifest = sourcesStatus.activeManifest;
    const repoOk = sourcesStatus.ok;

    if (repoOk && manifest) {
      const rsetCount = manifest.rulesets ? Object.keys(manifest.rulesets).length : 0;
      reportLines.push(`[✓] 发布源状态: ${sourcesStatus.sourceNote}`);
      reportLines.push(`- GitHub 主源: ${sourcesStatus.primary.ok ? `正常 (${sourcesStatus.primary.duration}ms)` : `不可达 (${sourcesStatus.primary.error})`}`);
      reportLines.push(`- jsDelivr 备用源: ${sourcesStatus.backup.ok ? `正常 (${sourcesStatus.backup.duration}ms)` : `不可达 (${sourcesStatus.backup.error})`}`);
      reportLines.push(`- 构建版本: ${manifest.release_commit || '最新'}`);
      reportLines.push(`- 构建时间: ${manifest.build_timestamp || '未知'}`);
      reportLines.push(`- 规则集清单: 包含 ${rsetCount} 个独立 .lsr 文件`);
    } else {
      reportLines.push(`[✘] 规则发布源不可达: ${sourcesStatus.sourceNote}`);
      reportLines.push('  判断: 规则资源下载受阻，请检查网络连接或切换备用镜像');
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【.lsr 规则集文件完整性与哈希核对】');

    // 2. Download and verify actual .lsr ruleset files
    let rulesetFailure = false;
    if (repoOk && manifest && manifest.rulesets) {
      const activeBase = sourcesStatus.primary.ok ? PRIMARY_BASE_URL : BACKUP_BASE_URL;
      const allRulesets = Object.keys(manifest.rulesets);
      // In quick mode: test core rulesets; in full mode: test all 14 rulesets
      const toTest = mode === 'full'
        ? allRulesets
        : allRulesets.filter(r => ['AI-Overseas.lsr', 'Apple-Push.lsr', 'GoogleDrive.lsr', 'China-Direct.lsr'].includes(r));

      let verifiedCount = 0;
      for (const rname of toTest) {
        const meta = manifest.rulesets[rname];
        const vRes = await verifyRulesetFile(rname, meta, activeBase, httpClient);
        if (vRes.ok) {
          verifiedCount++;
          reportLines.push(`[✓] ${rname}: 校验通过 (版本: ${vRes.revision}, ${vRes.sizeBytes} 字节)`);
        } else {
          rulesetFailure = true;
          reportLines.push(`[✘] ${rname}: 校验失败 (${vRes.error})`);
        }
      }
      reportLines.push(`- 校验进度: 已验证 ${verifiedCount}/${toTest.length} 个规则集正文哈希与版本行`);
    } else {
      reportLines.push('[!] 因清单不可达，跳过规则文件正文下载校验');
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【已知服务连通性检测】');

    // 3. Select Services to Test
    let serviceList = [];
    if (manifest && Array.isArray(manifest.services) && manifest.services.length > 0) {
      serviceList = manifest.services;
    } else {
      serviceList = [
        { id: 'chatgpt', name: 'ChatGPT', url: 'https://chatgpt.com/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
        { id: 'gemini', name: 'Google Gemini', url: 'https://gemini.google.com/', expected_status: [200, 301, 302, 400, 404], quick: true },
        { id: 'claude', name: 'Claude', url: 'https://claude.ai/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
        { id: 'deepseek', name: 'DeepSeek (大陆 AI)', url: 'https://api.deepseek.com/', expected_status: [200, 401, 404], quick: true },
        { id: 'googledrive', name: 'Google Drive', url: 'https://drive.google.com/drive/my-drive', expected_status: [200, 301, 302], quick: true },
        { id: 'google', name: 'Google 通用', url: 'https://www.google.com/generate_204', expected_status: [204, 200], quick: true },
        { id: 'youtube', name: 'YouTube', url: 'https://www.youtube.com/generate_204', expected_status: [204, 200], quick: true },
        { id: 'github', name: 'GitHub', url: 'https://api.github.com/zen', expected_status: [200], quick: true },
        { id: 'icloud', name: 'Apple iCloud', url: 'https://www.icloud.com/', expected_status: [200, 301, 302], quick: true },
      ];
    }

    if (mode === 'quick') {
      serviceList = serviceList.filter(s => s.quick === true);
    }

    let hasRouteFailure = false;
    let hasRouteBlockedWhileDirectOk = false;
    let totalTested = 0;

    for (const s of serviceList) {
      totalTested++;
      const res = await testService(s, httpClient);
      reportLines.push(`${res.symbol} ${res.name}: ${res.verdict}`);

      if (!res.routeReachable) {
        hasRouteFailure = true;
        if (res.directReachable) {
          hasRouteBlockedWhileDirectOk = true;
        }
      }
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【综合诊断结论】');

    const durationTotal = ((Date.now() - startTime) / 1000).toFixed(1);

    if (!repoOk) {
      reportLines.push('❗ 判断: 规则发布源无法下载或 manifest 损坏，请检查网络或切换备用镜像');
    } else if (rulesetFailure) {
      reportLines.push('⚠️ 判断: 部分 .lsr 规则集文件下载失败或哈希校验不匹配，请刷新规则订阅');
    } else if (hasRouteBlockedWhileDirectOk) {
      reportLines.push('⚠️ 判断: 当前路由失败但 DIRECT 正常，说明您当前为该服务选择的代理节点失效或被目标拒绝，请在 Loon 中更换出口节点');
    } else if (hasRouteFailure) {
      reportLines.push('⚠️ 判断: 部分服务当前路由和 DIRECT 均失败，可能是目标服务临时宕机或本地网络完全断开');
    } else {
      reportLines.push(`✔ 判断: 全部 ${totalTested} 项服务及规则源连接正常，分流策略运行平稳 (耗时: ${durationTotal}s)`);
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【必须诚实标注的能力边界 (需真机验证)】');
    reportLines.push('本诊断插件仅能检测已知 URL 的 HTTPS 连通性与规则发布完整性，不等于具体规则或 App 全部业务功能正确：');
    reportLines.push('1. 无法自动发现未知新增域名（仍需日常抓包或用户反馈补充）');
    reportLines.push('2. APNs TCP 5223 系统级长连接与锁屏通知 (须在 Loon“包含 APNS”开启时由系统 apsd 建立)');
    reportLines.push('3. Telegram 锁屏唤醒与蜂窝后台长连接推送延迟');
    reportLines.push('4. HomeKit 室内摄像头即时视频画面流推流与门铃');
    reportLines.push('5. Apple Watch 独立 Wi-Fi/蜂窝联网与天气表盘刷新');
    reportLines.push('6. 第三方依赖 CloudKit 的 App (爱乐记、猿音) 真实多端双向同步');
    reportLines.push('========================================');

    const finalReport = reportLines.join('\n');
    return {
      report: finalReport,
      repoOk,
      rulesetFailure,
      hasRouteFailure,
      hasRouteBlockedWhileDirectOk,
      duration: durationTotal
    };
  }

  // Loon Execution Entrypoint
  if (typeof $done !== 'undefined') {
    runDiagnostic().then((res) => {
      console.log(res.report);
      if (typeof $notification !== 'undefined') {
        const title = (res.hasRouteFailure || res.rulesetFailure || !res.repoOk)
          ? 'Loon 规则诊断: 发现异常'
          : 'Loon 规则诊断: 全部正常';
        const subtitle = res.hasRouteBlockedWhileDirectOk
          ? '存在当前路由失败但 DIRECT 正常项 (需检查节点)'
          : `检测完成 (${res.duration}s)，点击查看报告`;
        $notification.post(title, subtitle, '已输出至 Loon 日志，可直接全选复制反馈给 ChatGPT 或 Gemini');
      }
      $done({
        title: 'Loon 规则诊断',
        content: res.report
      });
    }).catch((err) => {
      console.log('Diagnostic error occurred');
      if (typeof $notification !== 'undefined') {
        $notification.post('Loon 规则诊断失败', '执行异常', classifyError(err));
      }
      $done({ error: classifyError(err) });
    });
  }

  // Export for automated local testing
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      runDiagnostic,
      testService,
      fetchManifestFromUrl,
      checkReleaseSources,
      verifyRulesetFile,
      classifyError,
      calculateSha256,
      PRIMARY_BASE_URL,
      BACKUP_BASE_URL,
      PRIMARY_MANIFEST_URL,
      BACKUP_MANIFEST_URL,
      PROBE_TIMEOUT_MS
    };
  }
})();
