import { afterEach, mock, test } from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl, createApi, filePayload, money } from '../src/api.ts';

afterEach(() => mock.restoreAll());
test('a captured workspace cannot change during a pending mutation', async () => {
  let release;
  let request;
  mock.method(globalThis, 'fetch', (url, options) => {
    request = { url, options };
    return new Promise((resolve) => {
      release = resolve;
    });
  });
  const demo = createApi('demo', 'demo-token');
  const pending = demo('documents/one/review', {
    case_id: 'line-two',
    verified: true,
    mapping_version: 'previous-review',
  });
  createApi('live', 'new-token');
  release(new Response(JSON.stringify({ saved: true })));
  assert.deepEqual(await pending, { saved: true });
  assert.equal(request.url, '/api/documents/one/review?workspace=demo');
  assert.equal(request.options.headers['X-ClaimLedger-Token'], 'demo-token');
  assert.deepEqual(JSON.parse(request.options.body), {
    case_id: 'line-two',
    verified: true,
    mapping_version: 'previous-review',
  });
});
test('preview page query keeps workspace isolation', () => {
  assert.equal(
    apiUrl('documents/one/preview?page=2', 'live'),
    '/api/documents/one/preview?page=2&workspace=live',
  );
});
test('backend conflict reason reaches the review form', async () => {
  mock.method(
    globalThis,
    'fetch',
    async () =>
      new Response(JSON.stringify({ error: 'Evidence changed; refresh before reviewing.' }), {
        status: 400,
      }),
  );
  await assert.rejects(
    createApi('demo', 'token')('documents/one/review', {}),
    /Evidence changed; refresh before reviewing/,
  );
});
test('workspace abort signal propagates to pending requests', async () => {
  const controller = new AbortController();
  controller.abort();
  mock.method(globalThis, 'fetch', async (_, options) => {
    assert.equal(options.signal, controller.signal);
    options.signal.throwIfAborted();
  });
  await assert.rejects(createApi('live', 'token', controller.signal)('cases'), {
    name: 'AbortError',
  });
});
test('oversized evidence is rejected before a browser reads its content', async () => {
  await assert.rejects(
    filePayload(new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.pdf')),
    /Maximum file size is 10 MB/,
  );
});
test('currency display retains exact minor units', () => {
  assert.equal(money(1001, 'GBP'), '£10.01');
  assert.match(money(1001, 'CAD'), /10\.01/);
});
