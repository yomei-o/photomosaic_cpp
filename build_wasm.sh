#!/bin/sh
# WASM をビルドして docs/photomosaic.js（wasm 埋め込みの 1 ファイル）を作る。
set -e
cd "$(dirname "$0")"
EMSDK=${EMSDK:-/c/prog/emsdk/emsdk}
export EM_CONFIG="$EMSDK/.emscripten"
EMCC="$EMSDK/upstream/emscripten/em++.exe"
"$EMCC" -O3 -std=c++17 -Icpp cpp/wasm_api.cpp -o docs/photomosaic.js \
  -sSINGLE_FILE=1 -sMODULARIZE=1 -sEXPORT_NAME=PhotomosaicModule -sALLOW_MEMORY_GROWTH=1 \
  -sMAXIMUM_MEMORY=2GB -sENVIRONMENT=web,worker,node \
  -sEXPORTED_FUNCTIONS=_pm_tile_size,_pm_reset,_pm_add_tile,_pm_set_target,_pm_build,_pm_render,_pm_out_w,_pm_out_h,_pm_distinct,_pm_tile_at,_malloc,_free \
  -sEXPORTED_RUNTIME_METHODS=HEAPU8
ls -la docs/photomosaic.js
