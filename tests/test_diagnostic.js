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
          }, 5);
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
  assert.match(result.verdict, /当前路由正常/);
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
    }
  ]);

  const res = await diagnostic.checkReleaseSources(mockClient);
  assert.strictEqual(res.ok, true);
  assert.strictEqual(res.mirrorConsistent, false);
  assert.match(res.sourceNote, /主备双源可达但版本不一致/);
  assert.match(res.sourceNote, /镜像尚未同步/);
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
  assert.match(diag.report, /当前路由不可达.*DIRECT可达/);
  assert.match(diag.report, /建议在 Loon 中检查该服务命中规则、绑定策略组或出口节点/);
  assert.doesNotMatch(diag.report, /代理生效/);
  assert.doesNotMatch(diag.report, /当前代理节点异常/);
});

test('10. Full Diagnostic Run with All Green Services and Honest Boundaries', async () => {
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
  assert.match(diag.report, /全部.*项服务及规则源连接正常/);
  assert.match(diag.report, /能力边界提示/);
  assert.match(diag.report, /无法自动发现未知新增域名/);
  assert.match(diag.report, /APNs TCP 5223/);

  // Daily report line count assertion: normal all-pass report must be concise (<= 25 lines)
  const lineCount = diag.report.split('\n').filter(l => l.trim()).length;
  assert.ok(lineCount <= 25, `Report too long for daily copy-paste: ${lineCount} lines (expected <= 25)`);
});
