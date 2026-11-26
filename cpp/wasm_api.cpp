// WASM の入口。JS は写真をほどいて RGBA を渡し、できた RGBA を canvas に置くだけ。
#include <cstdint>
#include "photomosaic.h"

static photomosaic::Mosaic g;
static std::vector<uint8_t> g_out;
static int g_ow = 0, g_oh = 0;

extern "C" {

int pm_tile_size() { return photomosaic::TILE; }
// タイルだけ捨てる（元の写真は残す）
void pm_reset() {
    g.tiles.clear(); g.tiles.shrink_to_fit();
    g.assign.clear(); g.uses.clear();
    g_out.clear(); g_out.shrink_to_fit();
}
int pm_add_tile(const uint8_t* rgba) {   // TILE x TILE の RGBA
    g.add_tile(rgba, photomosaic::TILE, photomosaic::TILE);
    return (int)g.tiles.size();
}
void pm_set_target(const uint8_t* rgba, int w, int h) { g.set_target(rgba, w, h); }

// 戻り値: 縦のマス数（失敗は 0）
int pm_build(int cols, double reuse, int no_repeat, int seed) {
    photomosaic::Options o;
    o.reuse = reuse; o.no_repeat = no_repeat; o.seed = (uint32_t)seed;
    return g.build(cols, o) ? g.rows : 0;
}

// 戻り値: 出力 RGBA の先頭（幅 pm_out_w、高さ pm_out_h）
uint8_t* pm_render(int cell, double blend) {
    g.render(cell, blend, g_out);
    g_ow = g.cols * cell; g_oh = g.rows * cell;
    return g_out.data();
}
int pm_out_w() { return g_ow; }
int pm_out_h() { return g_oh; }
int pm_distinct() { return g.distinct_used(); }
int pm_tile_at(int r, int c) { return (r >= 0 && c >= 0 && r < g.rows && c < g.cols) ? g.assign[r * g.cols + c] : -1; }

}
