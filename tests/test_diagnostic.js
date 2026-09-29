/**
 * Local Fixture Tests for loon-rules-diagnostic.js
 * Verifies all edge cases required by the specification and review:
 * 1. Millisecond Timeout Parameter Assertion (Loon official specification)
 * 2. Strict TLS Verification (insecure: false) and Cookie Isolation (auto-cookie: false)
 * 3. Error Classifier Mapping to Fixed Enums (Zero credential leakage)
 * 4. 401/403 treated as reachable for specific API endpoints
 * 5. Primary and Backup Release Mirror Inspection
 * 6. Pure JS SHA-256 Algorithm Verification (without crypto.subtle or Node require)
 * 7. Ruleset File Downloading, Non-empty Check, Revision Match, and SHA-256 Verification
 * 8. Ruleset File Download Fails on Injected Wrong SHA256, Empty Body, and Rule Count Mismatch
 * 9. Primary vs Backup Manifest Version Mismatch Detection
 * 10. Partial Service Failure with Neutral Phrasing (No claims of "proxy working" or "node broken")
 * 11. Concurrency, Execution Deadline Protection and Partial Reporting
 * 12. Concise Daily Report Length (<= 25 lines when all green)
 */

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const crypto = require('node:crypto');

const diagnostic = require(path.join(__dirname, '..', 'diagnostics', 'loon-rules-diagnostic.js'));

// Sample ruleset body and its actual sha256 & revision
const sampleRuleBody = "DOMAIN-SUFFIX,openai.com\nDOMAIN-SUFFIX,chatgpt.com";
const sampleSha256 = crypto.createHash('sha256').update(sampleRuleBody, 'utf8').digest('hex');
const sampleRevision = sampleSha256.slice(0, 12);

const sampleLsrContent = `# NAME: AI-Overseas
# DESCRIPTION: Overseas AI services
# AUTHOR: o-ocn
# REVISION: ${sampleRevision}
# TOTAL: 2
# ==============================================================================
${sampleRuleBody}
`;

// Mock manifest fixture
const sampleManifest = {
  schema_version: '1.0',
  build_timestamp: '2026-09-28T12:00:00Z',
  content_revision: 'abc123456789',
  package_sha256: 'abc123456789abcdef123456789abcdef123456789abcdef123456789abcdef12',
  release_commit: 'abc1234',
  rulesets: {
    'AI-Overseas.lsr': {
      total_rules: 2,
      revision: sampleRevision,
      sha256: sampleSha256,
      description: 'Overseas AI services'
    }
  },
  services: [
    {
      id: 'chatgpt',
      name: 'ChatGPT',
      category: 'AI-Overseas',
      url: 'https://chatgpt.com/favicon.ico',
      expected_status: [200, 401, 403],
      quick: true
    },
    {
      id: 'gemini',
      name: 'Google Gemini',
      category: 'AI-Overseas',
      url: 'https://gemini.google.com/',
      expected_status: [200, 301, 302, 400, 404],
      quick: true
    },
    {
      id: 'blocked_svc',
      name: 'Blocked Service',
      category: 'Test',
      url: 'https://blocked.example.com/',
      expected_status: [200],
      quick: true
    }
  ]
};

// Helper to create a mock $httpClient with strict parameter assertion
function createMockHttpClient(handlers) {
  return {
    get: function (opts, callback) {
      const url = opts.url;
      const isDirect = opts.node === 'DIRECT';

      // Strict assertions on Loon options
      assert.ok(
        typeof opts.timeout === 'number' && opts.timeout >= 1000,
        `Expected timeout in milliseconds (>= 1000 ms), got: ${opts.timeout}`
      );
      assert.strictEqual(opts.insecure, false, 'Expected insecure: false');
      assert.strictEqual(opts['auto-cookie'], false, 'Expected auto-cookie: false');

      for (const h of handlers) {
        if (h.matches(url, isDirect, opts)) {
          setTimeout(() => {
            if (h.error) {
              callback(h.error, null, null);
            } else {
              callback(null, { status: h.status || 200, headers: h.headers || {} }, h.data || '');
            }
          }, typeof h.delayMs === 'number' ? h.delayMs : 5);
          return;
        }
      }

      // Default fallback
      setTimeout(() => {
        callback(null, { status: 200, headers: {} }, 'OK');
      }, 5);
    }
  };
}

test('1. Loon Options: Milliseconds Timeout, Insecure False, and Auto-Cookie False', async () => {
  let verifiedOpts = null;
  const mockClient = {
    get: function (opts, callback) {
      verifiedOpts = opts;
      callback(null, { status: 200, headers: {} }, 'OK');
    }
  };

  await diagnostic.testService({ url: 'https://example.com' }, mockClient);
  assert.ok(verifiedOpts !== null);
  assert.strictEqual(verifiedOpts.timeout, diagnostic.PROBE_TIMEOUT_MS);
  assert.ok(verifiedOpts.timeout >= 1000, 'Timeout must be in milliseconds (>= 1000)');
  assert.strictEqual(verifiedOpts.insecure, false, 'Must enforce insecure: false');
  assert.strictEqual(verifiedOpts['auto-cookie'], false, 'Must enforce auto-cookie: false');
});

test('2. Error Classifier: Fixed Safe Enums Without Raw Leakage', () => {
  assert.strictEqual(diagnostic.classifyError('Request timed out after 5000ms'), '请求超时');
  assert.strictEqual(diagnostic.classifyError('connect TIMEOUT'), '请求超时');
  assert.strictEqual(diagnostic.classifyError('getaddrinfo ENOTFOUND chatgpt.com?token=secret123'), 'DNS解析失败');
  assert.strictEqual(diagnostic.classifyError('SSL routines:ssl3_read_bytes:tlsv1 alert'), 'TLS握手错误');
  assert.strictEqual(diagnostic.classifyError('certificate has expired'), 'TLS握手错误');
  assert.strictEqual(diagnostic.classifyError('connect ECONNREFUSED 127.0.0.1:80'), '连接被拒或重置');
  assert.strictEqual(diagnostic.classifyError('network is unreachable'), '网络不可达');
  assert.strictEqual(diagnostic.classifyError('Random uncaught internal error with user=admin&pass=123'), '未知错误');
});

test('3. 401/403 Status Treated as Server Reachable for Specific Endpoints', async () => {
  const service = {
    id: 'api_test',
    name: 'API Service',
    url: 'https://api.openai.com/v1/models',
    expected_status: [200, 401, 403]
  };

  const mockClient = createMockHttpClient([
    {
      matches: (url, isDirect) => !isDirect,
      status: 401,
      data: '{"error": "Unauthorized"}'
    },
    {
      matches: (url, isDirect) => isDirect,
      status: 401,
      data: '{"error": "Unauthorized"}'
    }
  ]);

  const result = await diagnostic.testService(service, mockClient);
  assert.strictEqual(result.routeReachable, true, '401 should be treated as reachable when in expected_status');
  assert.strictEqual(result.directReachable, true);
  assert.match(result.verdict, /当前路由可达/);
});

test('4. Primary and Backup Release Mirrors: Both Checked Independently', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      error: new Error('getaddrinfo ENOTFOUND raw.githubusercontent.com')
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    }
  ]);

  const res = await diagnostic.checkReleaseSources(mockClient);
  assert.strictEqual(res.ok, true);
  assert.strictEqual(res.primary.ok, false);
  assert.strictEqual(res.backup.ok, true);
  assert.match(res.sourceNote, /jsDelivr 备用加速源/);
  assert.strictEqual(res.activeManifest.release_commit, 'abc1234');
});

test('5. Pure JS SHA-256 Calculation Works in Isolated Runtime', () => {
  const testVectors = [
    { input: '', expected: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
    { input: 'hello', expected: '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824' },
    { input: sampleRuleBody, expected: sampleSha256 },
    { input: '中文字符与规则测试 🚀', expected: crypto.createHash('sha256').update('中文字符与规则测试 🚀', 'utf8').digest('hex') }
  ];

  for (const v of testVectors) {
    const pure = diagnostic.pureJsSha256(v.input);
    assert.strictEqual(pure, v.expected, `Pure JS SHA-256 failed for: ${v.input}`);

    const calc = diagnostic.calculateSha256(v.input);
    assert.strictEqual(calc.ok, true);
    assert.strictEqual(calc.hash, v.expected);
  }
});

test('6. Ruleset File Download and SHA-256 Integrity Verification', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url.includes('AI-Overseas.lsr'),
      status: 200,
      data: sampleLsrContent
    }
  ]);

  const meta = sampleManifest.rulesets['AI-Overseas.lsr'];
  const res = await diagnostic.verifyRulesetFile('AI-Overseas.lsr', meta, diagnostic.PRIMARY_BASE_URL, mockClient);

  assert.strictEqual(res.ok, true, `Verification failed with error: ${res.error}`);
  assert.strictEqual(res.revision, sampleRevision);
  assert.strictEqual(res.ruleCount, 2);
  assert.strictEqual(res.error, null);
});

test('7. Ruleset File Download Fails on Injected Wrong SHA256, Empty Body, and Rule Count Mismatch', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url.includes('TamperedRev.lsr'),
      status: 200,
      data: `# NAME: TamperedRev\n# REVISION: badrev123456\n# ==============================================================================\nDOMAIN,tampered.com\n`
    },
    {
      matches: (url) => url.includes('EmptyFile.lsr'),
      status: 200,
      data: ''
    },
    {
      matches: (url) => url.includes('WrongSha.lsr'),
      status: 200,
      data: `# NAME: WrongSha\n# REVISION: ${sampleRevision}\n# TOTAL: 2\n# ==============================================================================\nDOMAIN,tampered-rule.com\n`
    },
    {
      matches: (url) => url.includes('EmptyBody.lsr'),
      status: 200,
      data: `# NAME: EmptyBody\n# REVISION: ${sampleRevision}\n# ==============================================================================\n\n`
    },
    {
      matches: (url) => url.includes('CountMismatch.lsr'),
      status: 200,
      data: `# NAME: CountMismatch\n# REVISION: ${sampleRevision}\n# TOTAL: 5\n# ==============================================================================\nDOMAIN,rule1.com\n`
    }
  ]);

  // 1. Injected wrong SHA-256 must NOT be silently accepted
  const resWrongSha = await diagnostic.verifyRulesetFile(
    'WrongSha.lsr',
    { revision: sampleRevision, sha256: sampleSha256, total_rules: 1 },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resWrongSha.ok, false);
  assert.match(resWrongSha.error, /SHA256 校验和不匹配/);

  // 2. Empty rule body (only header, no body)
  const resEmptyBody = await diagnostic.verifyRulesetFile(
    'EmptyBody.lsr',
    { revision: sampleRevision, sha256: 'deadbeef' },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resEmptyBody.ok, false);
  assert.match(resEmptyBody.error, /规则正文为空/);

  // 3. Rule count mismatch
  const resCountMismatch = await diagnostic.verifyRulesetFile(
    'CountMismatch.lsr',
    { revision: sampleRevision, total_rules: 5 },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resCountMismatch.ok, false);
  assert.match(resCountMismatch.error, /规则条数不符/);

  // 4. Tampered revision
  const resTampered = await diagnostic.verifyRulesetFile(
    'TamperedRev.lsr',
    { revision: 'goodrev12345', sha256: 'deadbeef' },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resTampered.ok, false);
  assert.match(resTampered.error, /版本不匹配/);

  // 5. Empty file
  const resEmpty = await diagnostic.verifyRulesetFile(
    'EmptyFile.lsr',
    { revision: 'goodrev12345', sha256: 'deadbeef' },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resEmpty.ok, false);
  assert.match(resEmpty.error, /文件内容为空/);
});

test('8. Primary vs Backup Manifest Version Mismatch Detection', async () => {
  const backupMismatchedManifest = Object.assign({}, sampleManifest, {
    content_revision: 'different_hash_999',
    rulesets: {
      'AI-Overseas.lsr': {
        total_rules: 2,
        revision: 'oldrevision12',
        sha256: 'old_sha_256_hash_different'
      }
    }
  });

  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(backupMismatchedManifest)
    },
    {
      matches: (url) => url.includes('.lsr'),
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK'
    }
  ]);

  const res = await diagnostic.checkReleaseSources(mockClient);
  assert.strictEqual(res.ok, true);
  assert.strictEqual(res.primaryOk, true);
  assert.strictEqual(res.backupOk, true);
  assert.strictEqual(res.mirrorConsistent, false);
  assert.strictEqual(res.hasWarning, true);
  assert.match(res.sourceNote, /主备双源可达但版本不一致/);
  assert.match(res.sourceNote, /镜像尚未同步/);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'quick' });
  assert.strictEqual(diag.hasWarning, true);
  assert.match(diag.report, /\[!\] 发布源状态 \(警告\): 主备双源可达但版本不一致/);
  assert.match(diag.report, /⚠️ 诊断结论: 已检测核心服务连通性均正常，但发布源存在警告/);
  assert.doesNotMatch(diag.report, /✔ 诊断结论/);

  // Verify notification title in entrypoint reflects warning
  let postedNotif = null;
  diagnostic.initLoonEntrypoint({
    $done: () => {},
    $notification: { post: (t, s, b) => { postedNotif = { title: t, subtitle: s, body: b }; } },
    $httpClient: mockClient,
    args: { mode: 'quick' }
  });
  await new Promise(r => setTimeout(r, 60));
  assert.ok(postedNotif);
  assert.strictEqual(postedNotif.title, 'Loon 规则诊断: 存在警告');
  assert.match(postedNotif.subtitle, /发布源存在警告或镜像未同步/);
});

test('9. Partial Service Failure with Strictly Neutral Phrasing', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url.includes('AI-Overseas.lsr'),
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: (url, isDirect) => url.includes('chatgpt.com'),
      status: 200,
      data: 'OK'
    },
    {
      matches: (url, isDirect) => url.includes('gemini.google.com'),
      status: 200,
      data: 'OK'
    },
    {
      matches: (url, isDirect) => url.includes('blocked.example.com') && !isDirect,
      error: new Error('connect ECONNREFUSED')
    },
    {
      matches: (url, isDirect) => url.includes('blocked.example.com') && isDirect,
      status: 200,
      data: 'OK'
    }
  ]);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'quick' });
  assert.strictEqual(diag.hasRouteFailure, true);
  assert.strictEqual(diag.hasRouteBlockedWhileDirectOk, true);

  // Must use strictly neutral observation without asserting that proxy or node is broken
  assert.match(diag.report, /仅 DIRECT 可达.*当前路由不可达/);
  assert.match(diag.report, /建议在 Loon 中检查该服务命中规则、绑定策略组或出口节点/);
  assert.doesNotMatch(diag.report, /代理生效/);
  assert.doesNotMatch(diag.report, /当前代理节点异常/);
});

test('10. Objective Phrasing When All Services Are Reachable (Current Route & DIRECT Both Reachable)', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url.includes('.lsr'),
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: (url, isDirect) => !isDirect,
      status: 200,
      data: 'OK'
    },
    {
      matches: (url, isDirect) => isDirect,
      status: 200,
      data: 'OK'
    }
  ]);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'quick' });
  assert.strictEqual(diag.hasRouteFailure, false);
  assert.strictEqual(diag.hasRouteBlockedWhileDirectOk, false);
  assert.strictEqual(diag.repoOk, true);
  assert.strictEqual(diag.countBothPass, 3);
  assert.strictEqual(diag.countProxyOnly, 0);

  // Assert objective phrasing - never claim "分流有效运作" or "分流策略运行平稳"
  assert.match(diag.report, /全部 3 项服务当前路由与 DIRECT 均可达 \(双向均可达\)/);
  assert.match(diag.report, /✔ 诊断结论: 已检测核心服务连通性均正常 \(双向均可达\)；提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。/);
  assert.doesNotMatch(diag.report, /分流有效运作/);
  assert.doesNotMatch(diag.report, /分流策略运行平稳/);
  assert.doesNotMatch(diag.report, /日常抓包/);

  // Assert updated boundary wording
  assert.match(diag.report, /【能力边界提示 \(需真机验证\)】仅探测已知 HTTPS 端点，无法自动发现全部未知域名。/);
  assert.match(diag.report, /APNs TCP 5223/);

  // Verify notification title and subtitle in entrypoint
  let postedNotif = null;
  diagnostic.initLoonEntrypoint({
    $done: () => {},
    $notification: { post: (t, s, b) => { postedNotif = { title: t, subtitle: s, body: b }; } },
    $httpClient: mockClient,
    args: { mode: 'quick' }
  });

  await new Promise(r => setTimeout(r, 60));
  assert.ok(postedNotif, 'Notification must be posted');
  assert.strictEqual(postedNotif.title, 'Loon 规则诊断: 连通性正常');
  assert.doesNotMatch(postedNotif.title, /直连/, 'Notification title must never contain "直连"');
  assert.match(postedNotif.subtitle, /已检测 3 项服务均可达/);

  // Daily report line count assertion: normal all-pass report must be concise (<= 25 lines)
  const lineCount = diag.report.split('\n').filter(l => l.trim()).length;
  assert.ok(lineCount <= 25, `Report too long for daily copy-paste: ${lineCount} lines (expected <= 25)`);
});

test('11. 4-Way Routing States Distinction (Proxy-Only, Direct-Only, Both-Pass, Both-Fail)', async () => {
  // Test case where ChatGPT is proxy_only (routeReachable=true, directReachable=false)
  // Gemini is both_pass (routeReachable=true, directReachable=true)
  // Blocked is direct_only (routeReachable=false, directReachable=true)
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url.includes('.lsr'),
      status: 200,
      data: sampleLsrContent
    },
    {
      // ChatGPT: route ok, direct fails (proxy_only)
      matches: (url, isDirect) => url.includes('chatgpt.com') && !isDirect,
      status: 200,
      data: 'OK'
    },
    {
      matches: (url, isDirect) => url.includes('chatgpt.com') && isDirect,
      error: new Error('connect ETIMEDOUT')
    },
    {
      // Gemini: both ok (both_pass)
      matches: (url, isDirect) => url.includes('gemini.google.com'),
      status: 200,
      data: 'OK'
    },
    {
      // Blocked: route fails, direct ok (direct_only)
      matches: (url, isDirect) => url.includes('blocked.example.com') && !isDirect,
      error: new Error('connect ECONNREFUSED')
    },
    {
      matches: (url, isDirect) => url.includes('blocked.example.com') && isDirect,
      status: 200,
      data: 'OK'
    }
  ]);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'quick' });
  assert.strictEqual(diag.countProxyOnly, 1);
  assert.strictEqual(diag.countBothPass, 1);
  assert.strictEqual(diag.countDirectOnly, 1);
  assert.strictEqual(diag.countBothFail, 0);

  // Must clearly distinguish states in report using objective phrasing
  assert.match(diag.report, /仅当前路由可达: 1.*双向均可达: 1/);
  assert.match(diag.report, /仅 DIRECT 可达.*当前路由不可达/);
  assert.doesNotMatch(diag.report, /走代理分流/);
  assert.doesNotMatch(diag.report, /全部 3 项服务当前路由探测均正常/);

  // Test individual testService verdict for proxy_only
  const singleTest = await diagnostic.testService({ url: 'https://chatgpt.com', expected_status: [200] }, mockClient);
  assert.match(singleTest.verdict, /仅当前路由可达, DIRECT不可达/);
});

test('12. Entrypoint Watchdog Fires via Simulated Timer Callback and Emits Real Partial Report with Single $done Call', async () => {
  // Note: This test explicitly mocks setTimeout/clearTimeout to verify timer callback logic and scheduled delay values
  // (27000ms quick, 56000ms full) instantaneously; it does not claim to run 27/56 physical seconds on a real device.
  let donePayloads = [];
  let mockDone = (payload) => {
    donePayloads.push(payload);
  };

  // 1. Quick mode watchdog triggers at 27000ms
  let scheduledDelay = 0;
  let timerCallback = null;
  let mockSetTimeout = (cb, delay) => {
    scheduledDelay = delay;
    timerCallback = cb;
    return 12345;
  };
  let mockClearTimeout = () => {};

  // Setup slow client that responds for 1 service then hangs forever
  let mockHangingClient = {
    get: (opts, cb) => {
      if (opts.url && opts.url.includes('manifest.json')) {
        return cb(null, { status: 200 }, JSON.stringify(sampleManifest));
      }
      if (opts.url && opts.url.includes('.lsr')) {
        return cb(null, { status: 200 }, sampleLsrContent);
      }
      if (opts.url && opts.url.includes('chatgpt.com')) {
        return cb(null, { status: 200 }, 'OK');
      }
      // other services hang (never call cb)
    }
  };

  // Launch quick entrypoint
  const runner = diagnostic.initLoonEntrypoint({
    $done: mockDone,
    $httpClient: mockHangingClient,
    args: { mode: 'quick' },
    setTimeout: mockSetTimeout,
    clearTimeout: mockClearTimeout
  });

  assert.strictEqual(scheduledDelay, 27000, 'Quick mode watchdog must be scheduled at exactly 27000ms');

  // Wait a tick for manifest and chatgpt to finish
  await new Promise(r => setTimeout(r, 60));

  // Trigger watchdog manually (simulating 27s timer firing)
  assert.ok(timerCallback, 'Timer callback must be registered');
  timerCallback();

  assert.strictEqual(donePayloads.length, 1, '$done must be called exactly once by watchdog');
  assert.match(donePayloads[0].title, /快速模式超时/);
  assert.match(donePayloads[0].content, /时限保护 - 部分报告/);
  assert.match(donePayloads[0].content, /已完成服务探测/);
  assert.match(donePayloads[0].content, /在途网络请求未被底层 API 中断，但报告生成已截止/);

  // Verify $done is NOT called again even if called directly
  runner.safeDone({ error: 'Secondary call' });
  assert.strictEqual(donePayloads.length, 1, '$done must never be called multiple times');

  // 2. Full mode watchdog schedules at 56000ms
  scheduledDelay = 0;
  timerCallback = null;
  diagnostic.initLoonEntrypoint({
    $done: (p) => {},
    $httpClient: mockHangingClient,
    args: { mode: 'full' },
    setTimeout: (cb, d) => { scheduledDelay = d; return 999; },
    clearTimeout: () => {}
  });
  assert.strictEqual(scheduledDelay, 56000, 'Full mode watchdog must be scheduled at exactly 56000ms');
});

test('13. Backup Release Mirror Corruption Injection Detection in Full Mode Reflects Failures in Total State', async () => {
  // Test full mode verifying all rulesets from backup mirror
  const fullManifest = Object.assign({}, sampleManifest, {
    rulesets: {
      'AI-Overseas.lsr': { total_rules: 2, revision: sampleRevision, sha256: sampleSha256 },
      'GoogleDrive.lsr': { total_rules: 2, revision: sampleRevision, sha256: sampleSha256 }
    }
  });

  // Mock client where backup mirror GoogleDrive.lsr is corrupted (wrong SHA256)
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url.includes('manifest.json'),
      status: 200,
      data: JSON.stringify(fullManifest)
    },
    {
      matches: (url) => url.startsWith(diagnostic.PRIMARY_BASE_URL),
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: (url) => url === `${diagnostic.BACKUP_BASE_URL}/AI-Overseas.lsr`,
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: (url) => url === `${diagnostic.BACKUP_BASE_URL}/GoogleDrive.lsr`,
      status: 200,
      data: '# Corrupted backup content\nDOMAIN,corrupted.com\n'
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK'
    }
  ]);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'full' });
  assert.strictEqual(diag.rulesetFailure, true, 'Corrupted backup file must trigger rulesetFailure');
  assert.match(diag.report, /备用源: GoogleDrive.lsr 校验失败/);
  assert.match(diag.report, /部分 .lsr 规则集文件下载失败或哈希校验不匹配/);
});

test('14. HTTP 404 Reports Resource Missing or Not Yet Published and Skips Ruleset Body Check when Manifests Missing', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 404,
      data: '404 Not Found'
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 404,
      data: '404 Not Found'
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK'
    }
  ]);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'full' });
  assert.strictEqual(diag.repoOk, false);
  assert.match(diag.report, /HTTP 404 \(资源不存在或尚未发布\)/);
  assert.match(diag.report, /规则正文校验: 未执行 \(主备清单均不可用\)/);
  assert.doesNotMatch(diag.report, /\d+\/\d+ LSR 本地元数据校验匹配/);
});

test('15. Primary OK But Backup Mirror Down Emits Warning and Flags Notification', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 500,
      data: 'Server Error'
    },
    {
      matches: (url) => url.includes('.lsr'),
      status: 200,
      data: sampleLsrContent
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK'
    }
  ]);

  const res = await diagnostic.checkReleaseSources(mockClient);
  assert.strictEqual(res.primaryOk, true);
  assert.strictEqual(res.backupOk, false);
  assert.strictEqual(res.hasWarning, true);
  assert.strictEqual(res.isAllGood, false);
  assert.match(res.sourceNote, /GitHub 主源正常，jsDelivr 备用源不可达/);

  const diag = await diagnostic.runDiagnostic({ httpClient: mockClient, mode: 'quick' });
  assert.strictEqual(diag.hasWarning, true);
  assert.match(diag.report, /\[!\] 发布源状态 \(警告\): GitHub 主源正常，jsDelivr 备用源不可达/);
  assert.match(diag.report, /⚠️ 诊断结论: 已检测核心服务连通性均正常，但发布源存在警告/);
  assert.doesNotMatch(diag.report, /✔ 诊断结论/);

  // Notification title assertion: must flag warning, never green or direct
  let postedNotif = null;
  diagnostic.initLoonEntrypoint({
    $done: () => {},
    $notification: { post: (t, s, b) => { postedNotif = { title: t, subtitle: s, body: b }; } },
    $httpClient: mockClient,
    args: { mode: 'quick' }
  });
  await new Promise(r => setTimeout(r, 60));
  assert.ok(postedNotif);
  assert.strictEqual(postedNotif.title, 'Loon 规则诊断: 存在警告');
  assert.doesNotMatch(postedNotif.title, /连通性正常/);
  assert.doesNotMatch(postedNotif.title, /直连/);
  assert.match(postedNotif.subtitle, /发布源存在警告或镜像未同步/);
});

test('16. Backup Rulesets Incomplete Verification Due to Deadline Triggers Warning Not Green', async () => {
  // Build a manifest with 19 rulesets
  const rulesets19 = {};
  for (let i = 1; i <= 19; i++) {
    rulesets19[`Ruleset-${i}.lsr`] = {
      total_rules: 2,
      revision: sampleRevision,
      sha256: sampleSha256
    };
  }
  const manifest19 = Object.assign({}, sampleManifest, { rulesets: rulesets19 });

  const mockClient = createMockHttpClient([
    {
      matches: (url) => url.includes('manifest.json'),
      status: 200,
      data: JSON.stringify(manifest19)
    },
    {
      matches: (url) => url.startsWith(diagnostic.PRIMARY_BASE_URL),
      status: 200,
      data: sampleLsrContent,
      delayMs: 1
    },
    {
      matches: (url) => url.startsWith(diagnostic.BACKUP_BASE_URL),
      status: 200,
      data: sampleLsrContent,
      delayMs: 25 // delay per request so deadline cuts off backup verification
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK'
    }
  ]);

  // Set deadlineMs short so primary succeeds but backup checks exceed deadlineMs
  const diag = await diagnostic.runDiagnostic({
    httpClient: mockClient,
    mode: 'full',
    deadlineMs: 60
  });

  assert.strictEqual(diag.rulesetIncomplete, true, 'Ruleset verification must be flagged as incomplete');
  assert.strictEqual(diag.rulesetFailure, false, 'No files corrupted, only truncated');
  assert.match(diag.report, /\[!\] 备用源规则集: 未完成/);
  assert.doesNotMatch(diag.report, /\[✓\] 备用源规则集: 全部 14 个规则集 jsDelivr 镜像正文与 SHA256 均校验通过/);
  assert.match(diag.report, /⚠️ 诊断结论: 规则集校验因时限未完全完成，已完成部分有效/);
  assert.doesNotMatch(diag.report, /✔ 诊断结论/);

  // Notification title assertion: must flag warning, never green pass
  let postedNotif = null;
  diagnostic.initLoonEntrypoint({
    $done: () => {},
    $notification: { post: (t, s, b) => { postedNotif = { title: t, subtitle: s, body: b }; } },
    $httpClient: mockClient,
    args: { mode: 'full' },
    deadlineMs: 60
  });
  await new Promise(r => setTimeout(r, 120));
  assert.ok(postedNotif);
  assert.strictEqual(postedNotif.title, 'Loon 规则诊断: 存在警告');
  assert.doesNotMatch(postedNotif.title, /连通性正常/);
  assert.match(postedNotif.subtitle, /规则集校验未完全完成/);
});

test('17. Service Probing Incomplete Due to Deadline Triggers Warning and Never Green', async () => {
  // Build a manifest with 8 services to ensure concurrency limit (4) leaves remaining services unprobed
  const services8 = [];
  for (let i = 1; i <= 8; i++) {
    services8.push({ id: 'svc' + i, name: 'Service ' + i, url: 'https://svc' + i + '.com/ping', expected_status: [200], quick: true });
  }

  const manifest8 = Object.assign({}, sampleManifest, { services: services8 });

  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(manifest8),
      delayMs: 1
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(manifest8),
      delayMs: 1
    },
    {
      matches: (url) => url.includes('.lsr'),
      status: 200,
      data: sampleLsrContent,
      delayMs: 1
    },
    {
      matches: (url) => url.includes('svc1.com') || url.includes('svc2.com'),
      status: 200,
      data: 'OK',
      delayMs: 2
    },
    {
      matches: () => true,
      status: 200,
      data: 'OK',
      delayMs: 25
    }
  ]);

  // Set deadlineMs to 40ms: manifest & rulesets complete fast,
  // initial batch runs, then deadline is reached before all 8 services complete
  const diag = await diagnostic.runDiagnostic({
    httpClient: mockClient,
    mode: 'quick',
    deadlineMs: 40
  });

  assert.strictEqual(diag.rulesetIncomplete, false, 'Ruleset must be completely verified');
  assert.strictEqual(diag.rulesetFailure, false, 'No ruleset failure');
  assert.strictEqual(diag.serviceIncomplete, true, 'Service probing must be flagged incomplete');
  assert.ok(diag.totalTested < 8, `Expected totalTested < 8, got: ${diag.totalTested}`);
  assert.ok(diag.totalTested > 0, `Expected totalTested > 0, got: ${diag.totalTested}`);

  // Report must explicitly flag incomplete and never claim [✓] or green conclusion
  assert.match(diag.report, /\[!\] 服务连通性: 未完成 \(已探测 \d+\/8 项服务，当前路由均可达；部分项因时限跳过\)/);
  assert.match(diag.report, /⚠️ 诊断结论: 服务探测未完成 \(\d+\/8\)，已完成结果仅供参考；请在网络良好时重试完整探测。/);
  assert.doesNotMatch(diag.report, /✔ 诊断结论/);
  assert.doesNotMatch(diag.report, /\[✓\] 服务连通性/);

  // Notification title assertion: must flag warning, never green or direct
  let postedNotif = null;
  diagnostic.initLoonEntrypoint({
    $done: () => {},
    $notification: { post: (t, s, b) => { postedNotif = { title: t, subtitle: s, body: b }; } },
    $httpClient: mockClient,
    args: { mode: 'quick' },
    deadlineMs: 40
  });
  await new Promise(r => setTimeout(r, 250));
  assert.ok(postedNotif, 'Notification must be posted');
  assert.strictEqual(postedNotif.title, 'Loon 规则诊断: 存在警告');
  assert.doesNotMatch(postedNotif.title, /连通性正常/);
  assert.doesNotMatch(postedNotif.title, /直连/);
  assert.match(postedNotif.subtitle, /服务探测未完成 \(\d+\/8\)/);
});


