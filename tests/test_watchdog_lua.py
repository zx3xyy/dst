"""Execute generated console commands with strict Lua globals, like DST."""
import ctypes
import ctypes.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
import watchdog


class WatchdogLuaTests(unittest.TestCase):
    def lua(self, code):
        name = ctypes.util.find_library('lua5.4')
        if not name:
            self.skipTest('Install liblua5.4-0 to run Lua regression checks')
        lib = ctypes.CDLL(name)
        lib.luaL_newstate.restype = ctypes.c_void_p
        lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        lib.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
        lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        lib.lua_tolstring.restype = ctypes.c_char_p
        lib.lua_close.argtypes = [ctypes.c_void_p]
        state = lib.luaL_newstate()
        try:
            lib.luaL_openlibs(state)
            result = lib.luaL_loadstring(state, code.encode())
            if result == 0: result = lib.lua_pcallk(state, 0, 0, 0, 0, None)
            if result:
                self.fail(lib.lua_tolstring(state, -1, None).decode())
        finally:
            lib.lua_close(state)

    def gate_code(self, close):
        with patch.object(watchdog, 'command') as command:
            watchdog.gate('container', 'master', close)
            return command.call_args.args[2]

    def harness(self):
        return '''
        MARKER = "confirmed"
        print = function() end
        TheNet = {allowed=true}
        function TheNet:SetAllowNewPlayersToConnect(value) self.allowed=value end
        TheWorld = {}
        function TheWorld:DoStaticTaskInTime(delay, callback)
            assert(delay == 300)
            local task = {callback=callback, cancelled=false}
            function task:Cancel() self.cancelled=true end
            return task
        end
        setmetatable(_G, {
            __index=function(_, key) error("undeclared global: "..key) end,
            __newindex=function(_, key) error("new global: "..key) end
        })
        '''

    def test_close_refresh_reopen_and_expiry_with_strict_globals(self):
        close, reopen = self.gate_code(True), self.gate_code(False)
        self.lua(self.harness() + close + '''
            assert(not TheNet.allowed)
            local first=TheWorld._dstwatchdoglease
        ''' + close + '''
            assert(first.cancelled)
            local second=TheWorld._dstwatchdoglease
        ''' + reopen + '''
            assert(TheNet.allowed and second.cancelled)
            assert(TheWorld._dstwatchdoglease == nil)
        ''' + close + '''
            TheWorld._dstwatchdoglease.callback()
            assert(TheNet.allowed and TheWorld._dstwatchdoglease == nil)
        ''')

    def test_failed_lease_creation_does_not_close_connections(self):
        self.lua(self.harness() + '''
            TheWorld.DoStaticTaskInTime=function() error("scheduler unavailable") end
            local ok=pcall(function()
        ''' + self.gate_code(True) + '''
            end)
            assert(not ok and TheNet.allowed)
        ''')


if __name__ == '__main__': unittest.main()
