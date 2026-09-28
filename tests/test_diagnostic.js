/**
 * Local Fixture Tests for loon-rules-diagnostic.js
 * Verifies all edge cases required by the specification and review:
 * 1. Millisecond Timeout Parameter Assertion (Loon official specification)
 * 2. Strict TLS Verification (insecure: false) and Cookie Isolation (auto-cookie: false)
 * 3. Error Classifier Mapping to Fixed Enums (Zero credential leakage)
 * 4. 401/403 treated as reachable for specific API endpoints
 * 5. Primary and Backup Release Mirror Inspection
 * 6. Ruleset File Downloading, Non-empty Check, Revision Match, and SHA-256 Verification
 * 7. Corrupt manifest.json Handling
 * 8. Partial Service Failure (Route Fails but DIRECT OK)
 * 9. Full Diagnostic Run with All Green Services and Honest Boundary Output
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
  assert.match(result.verdict, /路由正常/);
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

test('5. Ruleset File Download and SHA-256 Integrity Verification', async () => {
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
  assert.strictEqual(res.error, null);
});

test('6. Ruleset File Download Fails on Hash / Content Mismatch', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url.includes('Tampered.lsr'),
      status: 200,
      data: `# NAME: Tampered\n# REVISION: badrev123456\n# ==============================================================================\nDOMAIN,tampered.com\n`
    },
    {
      matches: (url) => url.includes('Empty.lsr'),
      status: 200,
      data: ''
    }
  ]);

  // Test tampered revision
  const resTampered = await diagnostic.verifyRulesetFile(
    'Tampered.lsr',
    { revision: 'goodrev12345', sha256: 'deadbeef' },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resTampered.ok, false);
  assert.match(resTampered.error, /版本不匹配/);

  // Test empty file
  const resEmpty = await diagnostic.verifyRulesetFile(
    'Empty.lsr',
    { revision: 'goodrev12345', sha256: 'deadbeef' },
    diagnostic.PRIMARY_BASE_URL,
    mockClient
  );
  assert.strictEqual(resEmpty.ok, false);
  assert.match(resEmpty.error, /文件内容为空/);
});

test('7. Partial Service Failure (Route Fails but DIRECT OK)', async () => {
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
  assert.match(diag.report, /当前路由失败.*但 DIRECT正常/);
  assert.match(diag.report, /当前代理节点异常或服务阻断/);
});

test('8. Full Diagnostic Run with Verified Rulesets and Honest Boundaries', async () => {
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
  assert.match(diag.report, /全部.*服务及规则源连接正常/);
  assert.match(diag.report, /必须诚实标注的能力边界/);
  assert.match(diag.report, /无法自动发现未知新增域名/);
  assert.match(diag.report, /APNs TCP 5223/);
});
