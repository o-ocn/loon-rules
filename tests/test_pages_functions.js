const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(relative, overrides = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', 'functions', relative), 'utf8');
  const context = vm.createContext({ Request, Response, Headers, URL, TextEncoder, TextDecoder, Uint8Array,
    crypto: require('node:crypto').webcrypto, ...overrides });
  vm.runInContext(source.replaceAll('export async function ', 'async function '), context);
  return context;
}

test('subscription proxy permits only the intended methods, files and two-part paths', async () => {
  let calls = 0;
  const proxy = load('sub/[[catchall]].js', { fetch: async () => { calls++; return new Response('fixture'); } });
  for (const [parts, method, search] of [
    [['fixture-token-0001', 'other.txt'], 'GET', ''],
    [['fixture-token-0001', 'loon.txt', 'extra'], 'GET', ''],
    [['..', 'loon.txt'], 'GET', ''],
    [['fixture-token-0001', 'loon.txt'], 'POST', ''],
    [['fixture-token-0001', 'loon.txt'], 'GET', '?unexpected=1'],
  ]) {
    const response = await proxy.onRequest({ request: new Request('https://loon.rules.o-ous.com/sub/fixture' + search, { method }), params: { catchall: parts } });
    assert.ok([404, 405].includes(response.status));
  }
  assert.equal(calls, 0);
});

test('subscription proxy drops credentials and redirects and prevents private response caching', async () => {
  let redirects = false;
  const proxy = load('sub/[[catchall]].js', { fetch: async (url, options) => {
    assert.equal(new URL(url).pathname, '/fixture-token-0001/loon.txt');
    assert.equal(options.headers.has('Cookie'), false);
    assert.equal(options.headers.has('Authorization'), false);
    assert.equal(options.redirect, 'manual');
    return redirects ? new Response(null, { status: 302, headers: { Location: 'https://outside.invalid/' } })
      : new Response('fixture', { headers: { 'Set-Cookie': 'fixture', 'Subscription-Userinfo': 'fixture', 'Cache-Control': 'public' } });
  } });
  const context = { request: new Request('https://loon.rules.o-ous.com/sub/fixture', { headers: { Cookie: 'fixture', Authorization: 'fixture' } }), params: { catchall: ['fixture-token-0001', 'loon.txt'] } };
  const response = await proxy.onRequest(context);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), 'fixture');
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.equal(response.headers.has('Set-Cookie'), false);
  assert.equal(response.headers.get('Subscription-Userinfo'), 'fixture');
  redirects = true;
  assert.equal((await proxy.onRequest(context)).status, 502);
});

test('unlock rejects empty input and wrong passwords without releasing a subscription', async () => {
  const unlock = load('api/unlock.js', { crypto: { subtle: { importKey: async () => { throw new Error('fixture failure'); } } } });
  for (const [value, status] of [['', 400], ['deliberately-invalid-fixture', 401]]) {
    const response = await unlock.onRequestPost({ request: new Request('https://loon.rules.o-ous.com/api/unlock', { method: 'POST', body: JSON.stringify({ password: value }) }) });
    assert.equal(response.status, status);
    assert.equal((await response.json()).subscription_url, undefined);
  }
});

test('unlock does not trust arbitrary forwarded hosts; happy path uses synthetic crypto only', async () => {
  const unlock = load('api/unlock.js', { crypto: { subtle: {
    importKey: async () => ({}), deriveKey: async () => ({}),
    decrypt: async () => new TextEncoder().encode('fixture-token-0001'),
  } } });
  for (const forwarded of ['outside.invalid', 'loon.rules.o-ous.com']) {
    const fixturePassword = 'fixture';
    const response = await unlock.onRequestPost({ request: new Request('https://loon-rules-ctp.pages.dev/api/unlock', {
      method: 'POST', headers: { 'x-forwarded-host': forwarded }, body: JSON.stringify({ password: fixturePassword, client: 'loon' }),
    }) });
    const data = await response.json();
    assert.equal(response.status, 200);
    assert.equal(new URL(data.subscription_url).hostname, forwarded === 'outside.invalid' ? 'loon-rules-ctp.pages.dev' : forwarded);
    assert.ok(data.import_url.startsWith('loon://import?nodelist='));
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
  }

  // Also verify clash client produces clash:// URL scheme
  const fixtureClashPassword = 'fixture';
  const clashResponse = await unlock.onRequestPost({ request: new Request('https://loon-rules-ctp.pages.dev/api/unlock', {
    method: 'POST', body: JSON.stringify({ password: fixtureClashPassword, client: 'clash' }),
  }) });
  const clashData = await clashResponse.json();
  assert.equal(clashResponse.status, 200);
  assert.ok(clashData.import_url.startsWith('clash://install-config?url='));
});
