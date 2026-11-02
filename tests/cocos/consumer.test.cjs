const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

function consumer({ persisted = {}, migrationFails = false } = {}) {
    const values = new Map(Object.entries(persisted));
    const requests = [];
    const exports = {};
    const context = {
        exports, console, setTimeout,
        cc: { sys: {
            localStorage: { getItem: key => values.get(key) ?? null,
                setItem: (key, value) => values.set(key, value) },
            isNative: false, isBrowser: true, os: 'test', osVersion: '1',
            language: 'en', OS_IOS: 'iOS', OS_OSX: 'OS X', OS_ANDROID: 'Android',
        } },
        fetch: async (url, options) => {
            assert.ok(url.startsWith('https://sdk.invalid/'));
            const path = new URL(url).pathname;
            requests.push({ path, ...options, json: options.body ? JSON.parse(options.body) : null });
            let body = {};
            let status = 200;
            if (path.endsWith('/migrate') && migrationFails) status = 404;
            else if (path.endsWith('/anonymous') || path.endsWith('/migrate'))
                body = { accessToken: 'fixture-access', refreshToken: 'fixture-refresh', userId: 'fixture-user' };
            else if (path.endsWith('/session/start')) body = { sessionId: 'fixture-session' };
            return { ok: status === 200, status, json: async () => body,
                text: async () => JSON.stringify(body) };
        },
    };
    vm.runInNewContext(readFileSync(join(process.env.SDK_JS, 'CubeageSDK.js'), 'utf8'), context);
    return { sdk: exports.default.instance, requests, values };
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('source package default and named entrypoints support anonymous initialization and events', async () => {
    const { sdk, requests, values } = consumer();
    await sdk.init({ apiBaseUrl: 'https://sdk.invalid/', gameSlug: 'fixture-game' });
    await tick();
    assert.equal(sdk.isInitialized, true);
    assert.equal(sdk.userId, 'fixture-user');
    assert.equal(sdk.sessionId, 'fixture-session');
    assert.equal(values.get('cubeage_access_token'), 'fixture-access');
    const device = values.get('cubeage_device_id');
    assert.match(device, /^[0-9a-f-]{36}$/);
    assert.equal(requests[0].path, '/api/v1/sdk/auth/anonymous');
    assert.equal(requests[0].json.deviceId, device);
    sdk.trackEvent('fixture_event', { count: 2 });
    await tick();
    const event = requests.find(r => r.path.endsWith('/event/batch'));
    assert.deepEqual(event.json, { gameSlug: 'fixture-game', events: [{ name: 'fixture_event', properties: { count: 2 } }] });
    assert.equal(event.headers.Authorization, 'Bearer fixture-access');
    const count = requests.length;
    await sdk.init({ apiBaseUrl: 'https://ignored.invalid', gameSlug: 'ignored' });
    assert.equal(requests.length, count);
});

test('persisted identity bypasses auth and retains the existing device id', async () => {
    const { sdk, requests, values } = consumer({ persisted: {
        cubeage_access_token: 'persisted-access', cubeage_user_id: 'persisted-user',
        cubeage_device_id: 'persisted-device', cubeage_first_launch: '1',
    } });
    await sdk.init({ apiBaseUrl: 'https://sdk.invalid', gameSlug: 'fixture-game' });
    await tick();
    assert.equal(sdk.userId, 'persisted-user');
    assert.equal(values.get('cubeage_device_id'), 'persisted-device');
    assert.equal(requests.some(r => r.path.includes('/auth/') || r.path.endsWith('/migrate')), false);
});

for (const migrationFails of [false, true]) test(`legacy migration preserves fallback behavior (failure=${migrationFails})`, async () => {
    const { sdk, requests, values } = consumer({ persisted: { legacy_device: 'legacy-fixture' }, migrationFails });
    await sdk.init({ apiBaseUrl: 'https://sdk.invalid', gameSlug: 'fixture-game', legacyTokenKey: 'legacy_device' });
    await tick();
    assert.equal(sdk.userId, 'fixture-user');
    assert.equal(requests[0].path, '/api/v1/sdk/migrate');
    assert.equal(requests[0].json.token, 'legacy-fixture');
    assert.equal(requests.some(r => r.path.endsWith('/anonymous')), migrationFails);
    assert.equal(values.get('cubeage_migration_done'), '1');
    assert.equal(values.get('legacy_device'), 'legacy-fixture');
});
