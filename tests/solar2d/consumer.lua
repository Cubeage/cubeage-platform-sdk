-- Consumer of the unpacked Lua package, with deterministic Solar2D host boundaries.
-- JSON is Solar2D's real json/dkjson implementation; HTTP never leaves this process.
local json = require('json')
package.preload.lfs = function() return {} end -- imported, but unused by this SDK
local requests, listeners = {}, {}
local directory = assert(os.getenv('SDK_TEST_DATA'))
system = {
    DocumentsDirectory = 'documents',
    pathForFile = function(name) return directory .. '/' .. name end,
    getInfo = function(key)
        return ({ deviceID = 'fixture-device', platform = 'android', model = 'fixture',
            platformVersion = '1', appVersionString = '1.0' })[key]
    end,
    getPreference = function(_, key) return key == 'language' and 'en' or 'US' end,
}
timer = { performWithDelay = function(_, callback) callback() end }
Runtime = { addEventListener = function(_, event, callback) listeners[event] = callback end }
package.preload.network = function() return {
    request = function(url, method, callback, params)
        assert(url:match('^https://sdk%.invalid/api/'))
        local path = url:sub(#'https://sdk.invalid' + 1)
        local request = { path = path, method = method, headers = params.headers,
            body = params.body and json.decode(params.body) }
        requests[#requests + 1] = request
        local body = {}
        if path == '/api/v1/sdk/auth/anonymous' then
            body = { accessToken = 'fixture-access', refreshToken = 'fixture-refresh', userId = 'fixture-user' }
        elseif path:match('/config$') then body = { config = { difficulty = 'normal', enabled = false } }
        elseif path == '/api/v1/sdk/session/start' then body = { sessionId = 'fixture-session' }
        elseif path == '/api/v1/sdk/session/end' then body = { durationSeconds = 12 }
        end
        callback({ isError = false, status = 200, response = json.encode(body) })
    end,
} end
local sdk = require('cubeage_sdk')
local config = require('cubeage_sdk_config')
assert(config.appKey and config.sdkVersion and config.apiBaseUrl)
assert(sdk.isInitialized() == false)
assert(sdk.getConfig('missing', 'default') == 'default')
local errorSeen
sdk.checkForUpdate(nil, function(err) errorSeen = err end)
assert(errorSeen == 'Not initialized')
-- Calls before initialization must not create a request.
sdk.trackEvent('ignored')
sdk.startSession()
assert(#requests == 0)
local done
sdk.init({ apiBaseUrl = 'https://sdk.invalid/', appKey = 'fixture-game' },
    function(remote) done = remote end, function(err) error(err) end)
assert(done.difficulty == 'normal')
assert(sdk.isInitialized() and sdk.getUserId() == 'fixture-user')
assert(sdk.getSessionId() == 'fixture-session')
assert(sdk.getConfig('enabled', true) == false)
assert(requests[1].path == '/api/v1/sdk/auth/anonymous')
assert(requests[1].body.deviceId == 'fixture-device')
sdk.trackEvent('fixture_event', { count = 2 })
local event = requests[#requests]
assert(event.path == '/api/v1/sdk/event/batch')
assert(event.headers.Authorization == 'Bearer fixture-access')
assert(event.body.events[1].name == 'fixture_event')
assert(event.body.events[1].properties.count == 2)
local duration
sdk.endSession(function(seconds) duration = seconds end)
assert(duration == 12 and sdk.getSessionId() == nil)
listeners.system({ type = 'applicationResume' })
assert(sdk.getSessionId() == 'fixture-session')
listeners.system({ type = 'applicationSuspend' })
assert(sdk.getSessionId() == nil)
-- A new module instance must preserve the persisted identity without authenticating.
package.loaded.cubeage_sdk = nil
requests = {}
local restored = require('cubeage_sdk')
restored.init({ apiBaseUrl = 'https://sdk.invalid', appKey = 'fixture-game' }, function() end, error)
assert(restored.getUserId() == 'fixture-user')
for _, request in ipairs(requests) do assert(request.path ~= '/api/v1/sdk/auth/anonymous') end
print('Solar2D packaged consumer tests passed')
