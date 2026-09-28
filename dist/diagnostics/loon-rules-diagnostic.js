/**
 * Loon Rules Diagnostic Script (Strategy-Neutral, Zero-Privacy, Safe Read-Only)
 * Target Environment: Loon Generic Script (iOS / iPadOS / macOS)
 * Author: o-ocn
 * License: GPL-2.0
 */

(function () {
  'use strict';

  // Config constants
  const PRIMARY_MANIFEST_URL = 'https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/manifest.json';
  const BACKUP_MANIFEST_URL = 'https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/diagnostics/manifest.json';
  const DEFAULT_TIMEOUT_MS = 5000;
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

  // HTTP helper wrapper around Loon's $httpClient
  function httpRequest(options, httpClientInstance) {
    const client = httpClientInstance || (typeof $httpClient !== 'undefined' ? $httpClient : null);
    if (!client) {
      return Promise.reject(new Error('Loon $httpClient not available'));
    }

    const opts = Object.assign({
      timeout: DEFAULT_TIMEOUT_MS / 1000,
      headers: { 'User-Agent': USER_AGENT }
    }, options);

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

  // Classify network errors
  function classifyError(errStr) {
    if (!errStr) return '未知错误';
    const lower = errStr.toLowerCase();
    if (lower.includes('timeout') || lower.includes('timed out')) return '请求超时';
    if (lower.includes('dns') || lower.includes('resolve') || lower.includes('nodename') || lower.includes('enotfound') || lower.includes('getaddrinfo')) return 'DNS解析失败';
    if (lower.includes('tls') || lower.includes('ssl') || lower.includes('certificate') || lower.includes('handshake')) return 'TLS握手错误';
    if (lower.includes('refused') || lower.includes('reset') || lower.includes('abort') || lower.includes('econnrefused')) return '连接被拒或重置';
    return errStr.slice(0, 30);
  }

  // Load manifest with automatic primary -> backup fallback
  async function fetchManifest(httpClient) {
    const primaryRes = await httpRequest({ url: PRIMARY_MANIFEST_URL, timeout: 4 }, httpClient);
    if (primaryRes.ok && (primaryRes.status === 200 || primaryRes.status === 304)) {
      try {
        const manifest = JSON.parse(primaryRes.data);
        return { ok: true, source: 'GitHub官方源', manifest, error: null };
      } catch (e) {
        // Fall through to backup
      }
    }

    const backupRes = await httpRequest({ url: BACKUP_MANIFEST_URL, timeout: 5 }, httpClient);
    if (backupRes.ok && (backupRes.status === 200 || backupRes.status === 304)) {
      try {
        const manifest = JSON.parse(backupRes.data);
        return { ok: true, source: 'jsDelivr加速源 (GitHub主源异常)', manifest, error: null };
      } catch (e) {
        return { ok: false, source: '均不可达', manifest: null, error: 'manifest 数据解析失败' };
      }
    }

    return {
      ok: false,
      source: '均不可达',
      manifest: null,
      error: `主源错误: ${classifyError(primaryRes.error)}, 备用源错误: ${classifyError(backupRes.error)}`
    };
  }

  // Test single service endpoint on current route and DIRECT
  async function testService(service, httpClient) {
    const expected = service.expected_status || [200, 204];

    // Current route request (via Loon proxy / rule matching)
    const routeRes = await httpRequest({
      url: service.url,
      method: service.method || 'GET',
      timeout: 4
    }, httpClient);

    // DIRECT request (forced bypass)
    const directRes = await httpRequest({
      url: service.url,
      method: service.method || 'GET',
      node: 'DIRECT',
      timeout: 4
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
      verdict = `当前路由失败(${classifyError(routeRes.error) || 'HTTP ' + routeRes.status}) 但 DIRECT正常 (当前代理节点异常或服务阻断!)`;
    } else {
      symbol = '⚠';
      verdict = `当前路由与DIRECT均失败 (路由: ${classifyError(routeRes.error) || 'HTTP ' + routeRes.status}, DIRECT: ${classifyError(directRes.error)})`;
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
    reportLines.push(`诊断模式: ${mode === 'full' ? '完整诊断 (全量规则与服务)' : '快速诊断 (核心服务)'} | 生成时间: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC`);
    reportLines.push('----------------------------------------');

    // 1. Repo & Manifest Status
    reportLines.push('【规则仓库与发布状态】');
    const manifestResult = await fetchManifest(httpClient);

    let manifest = null;
    let repoOk = false;

    if (manifestResult.ok && manifestResult.manifest) {
      manifest = manifestResult.manifest;
      repoOk = true;
      const rsetCount = manifest.rulesets ? Object.keys(manifest.rulesets).length : 0;
      reportLines.push(`[✓] 仓库接入: 正常 (${manifestResult.source})`);
      reportLines.push(`- 构建版本: ${manifest.release_commit || '最新'}`);
      reportLines.push(`- 构建时间: ${manifest.build_timestamp || '未知'}`);
      reportLines.push(`- 规则集清单: 包含 ${rsetCount} 个独立 .lsr 文件`);
    } else {
      reportLines.push(`[✘] 仓库接入异常: ${manifestResult.error || '无法读取 manifest'}`);
      reportLines.push('  判断: 规则资源下载受阻或版本清单异常，请检查 GitHub 访问网络');
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【已知服务连通性检测】');

    // 2. Select Services to Test
    let serviceList = [];
    if (manifest && Array.isArray(manifest.services) && manifest.services.length > 0) {
      serviceList = manifest.services;
    } else {
      // Hardcoded fallback list if manifest is unavailable
      serviceList = [
        { id: 'chatgpt', name: 'ChatGPT', url: 'https://chatgpt.com/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
        { id: 'gemini', name: 'Google Gemini', url: 'https://gemini.google.com/', expected_status: [200, 301, 302, 400, 404], quick: true },
        { id: 'claude', name: 'Claude', url: 'https://claude.ai/favicon.ico', expected_status: [200, 301, 302, 401, 403], quick: true },
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
      reportLines.push('❗ 判断: 规则资源无法下载或 manifest 损坏，请检查网络或切换备用镜像');
    } else if (hasRouteBlockedWhileDirectOk) {
      reportLines.push('⚠️ 判断: 当前路由失败但 DIRECT 正常，说明您当前为该服务选择的代理节点失效或被目标拒绝，请在 Loon 中更换出口节点');
    } else if (hasRouteFailure) {
      reportLines.push('⚠️ 判断: 部分服务当前路由和 DIRECT 均失败，可能是目标服务临时宕机或本地网络完全断开');
    } else {
      reportLines.push(`✔ 判断: 全部 ${totalTested} 项服务及规则源连接正常，分流策略运行平稳 (耗时: ${durationTotal}s)`);
    }

    reportLines.push('----------------------------------------');
    reportLines.push('【必须诚实标注的能力边界 (需真机验证)】');
    reportLines.push('本诊断插件仅能检测 HTTP/HTTPS 端口与静态路由可达性，以下底层行为必须在 iPhone 真机核验：');
    reportLines.push('1. APNs TCP 5223 守护进程连接 (需在 Loon“包含 APNS”开启时捕获)');
    reportLines.push('2. Telegram 锁屏唤醒与蜂窝后台长连接推送延迟');
    reportLines.push('3. HomeKit 室内摄像头即时视频画面流推流与门铃');
    reportLines.push('4. Apple Watch 独立 Wi-Fi/蜂窝联网与天气表盘刷新');
    reportLines.push('5. 第三方依赖 CloudKit 的 App (爱乐记、猿音) 真实多端双向同步');
    reportLines.push('========================================');

    const finalReport = reportLines.join('\n');
    return {
      report: finalReport,
      repoOk,
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
        const title = res.hasRouteFailure ? 'Loon 规则诊断: 发现异常' : 'Loon 规则诊断: 全部正常';
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
      console.log('Diagnostic fatal error: ' + err);
      if (typeof $notification !== 'undefined') {
        $notification.post('Loon 规则诊断失败', '执行异常', err.toString());
      }
      $done({ error: err.toString() });
    });
  }

  // Export for automated local testing
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      runDiagnostic,
      testService,
      fetchManifest,
      classifyError,
      PRIMARY_MANIFEST_URL,
      BACKUP_MANIFEST_URL
    };
  }
})();
