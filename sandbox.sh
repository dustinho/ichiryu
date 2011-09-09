#!/bin/bash
ulimit -t 3 -m 300000
luajit sandbox.lua lua_in.lua
