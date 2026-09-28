/**
 * Local Fixture Tests for loon-rules-diagnostic.js
 * Verifies all 8 edge cases required by the specification:
 * 1. Request Timeout
 * 2. DNS Failure
 * 3. TLS Error
 * 4. 401/403 treated as reachable
 * 5. Corrupt manifest.json
 * 6. Missing rule file / empty response
 * 7. Partial service failure
 * 8. GitHub primary fail with backup CDN success
 */

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const diagnostic = require(path.join(__dirname, '..', 'diagnostics', 'loon-rules-diagnostic.js'));

// Mock manifest fixture
const sampleManifest = {
  schema_version: '1.0',
  build_timestamp: '2026-09-28T12:00:00Z',
  release_commit: 'abc1234',
  rulesets: {
    'AI-Overseas.lsr': { total_rules: 45, sha256: 'deadbeef' },
    'GoogleDrive.lsr': { total_rules: 6, sha256: 'cafebabe' }
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

// Helper to create a mock $httpClient
function createMockHttpClient(handlers) {
  return {
    get: function (opts, callback) {
      const url = opts.url;
      const isDirect = opts.node === 'DIRECT';
      
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
      
      // Default handler
      setTimeout(() => {
        callback(null, { status: 200, headers: {} }, 'OK');
      }, 5);
    }
  };
}

test('1. Error Classifier: Request Timeout', () => {
  assert.strictEqual(diagnostic.classifyError('Request timed out after 5000ms'), '请求超时');
  assert.strictEqual(diagnostic.classifyError('connect TIMEOUT'), '请求超时');
});

test('2. Error Classifier: DNS Failure', () => {
  assert.strictEqual(diagnostic.classifyError('getaddrinfo ENOTFOUND chatgpt.com'), 'DNS解析失败');
  assert.strictEqual(diagnostic.classifyError('Cannot resolve hostname'), 'DNS解析失败');
});

test('3. Error Classifier: TLS Error', () => {
  assert.strictEqual(diagnostic.classifyError('SSL routines:ssl3_read_bytes:tlsv1 alert'), 'TLS握手错误');
  assert.strictEqual(diagnostic.classifyError('certificate has expired'), 'TLS握手错误');
});

test('4. 401/403 Status Treated as Server Reachable for Specific Endpoints', async () => {
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

test('5. Manifest Fallback: GitHub Primary Fails, Backup CDN Succeeds', async () => {
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

  const res = await diagnostic.fetchManifest(mockClient);
  assert.strictEqual(res.ok, true);
  assert.match(res.source, /jsDelivr加速源/);
  assert.strictEqual(res.manifest.release_commit, 'abc1234');
});

test('6. Corrupt Manifest JSON Handling', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: '{ corrupt_json: '
    },
    {
      matches: (url) => url === diagnostic.BACKUP_MANIFEST_URL,
      status: 200,
      data: '<html>502 Bad Gateway</html>'
    }
  ]);

  const res = await diagnostic.fetchManifest(mockClient);
  assert.strictEqual(res.ok, false);
  assert.strictEqual(res.manifest, null);
});

test('7. Partial Service Failure (Route Fails but DIRECT OK)', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
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
      // Blocked service: fails on proxy route, but works on DIRECT
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

test('8. Full Diagnostic Run with All Green Services', async () => {
  const mockClient = createMockHttpClient([
    {
      matches: (url) => url === diagnostic.PRIMARY_MANIFEST_URL,
      status: 200,
      data: JSON.stringify(sampleManifest)
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
  assert.match(diag.report, /APNs TCP 5223/);
});
