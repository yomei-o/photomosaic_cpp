// photomosaic.h — たくさんの小さな写真（タイル）で 1 枚の大きな写真を描く。ヘッダオンリー、依存なし。
//
//   Mosaic m;
//   m.add_tile(rgba, TILE, TILE);     // 正方形に切り抜き済みのタイル（TILE x TILE）を何枚でも
//   m.set_target(rgba, w, h);         // 元にする写真
//   m.build(cols, opt);               // マスの割り当て
//   m.render(cell, blend, out);       // 1 マス cell 画素で描く。blend 0..1 はマスの色への寄せ具合
//
// 色は Lab（人の目の差に近い色空間）で、マスとタイルをそれぞれ 3x3 に区切った 9 か所の平均を比べる。
#pragma once
#include <vector>
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <limits>

namespace photomosaic {

static const int TILE = 64;      // タイルを持っておく大きさ
static const int SUB = 3;        // 特徴は SUB x SUB の平均色
static const int FDIM = SUB * SUB * 3;

// ---------------------------------------------------------------- 色
inline double srgb_to_linear(double c) {
    c /= 255.0;
    return c <= 0.04045 ? c / 12.92 : std::pow((c + 0.055) / 1.055, 2.4);
}

inline const double* lin_table() {
    static double t[256];
    static bool init = false;
    if (!init) { for (int i = 0; i < 256; i++) t[i] = srgb_to_linear(i); init = true; }
    return t;
}

inline double lab_f(double t) {
    const double d = 6.0 / 29.0;
    return t > d * d * d ? std::cbrt(t) : t / (3 * d * d) + 4.0 / 29.0;
}

// 線形 RGB（0..1）の平均 → Lab。平均は線形のまま取ってから変換する。
inline void linear_to_lab(double r, double g, double b, double lab[3]) {
    double X = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047;
    double Y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b);
    double Z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883;
    double fx = lab_f(X), fy = lab_f(Y), fz = lab_f(Z);
    lab[0] = 116 * fy - 16;
    lab[1] = 500 * (fx - fy);
    lab[2] = 200 * (fy - fz);
}

// rgba 画像の矩形 [x0,x1)x[y0,y1) を SUB x SUB に区切った Lab 特徴と、全体の平均 RGB（sRGB 値）
inline void features(const uint8_t* rgba, int w, double x0, double y0, double x1, double y1,
                     double feat[FDIM], double mean_rgb[3]) {
    const double* L = lin_table();
    double tr = 0, tg = 0, tb = 0; long tn = 0;
    for (int sy = 0; sy < SUB; sy++)
        for (int sx = 0; sx < SUB; sx++) {
            int ax = (int)std::floor(x0 + (x1 - x0) * sx / SUB), bx = (int)std::floor(x0 + (x1 - x0) * (sx + 1) / SUB);
            int ay = (int)std::floor(y0 + (y1 - y0) * sy / SUB), by = (int)std::floor(y0 + (y1 - y0) * (sy + 1) / SUB);
            if (bx <= ax) bx = ax + 1;
            if (by <= ay) by = ay + 1;
            double r = 0, g = 0, b = 0; long n = 0;
            for (int y = ay; y < by; y++)
                for (int x = ax; x < bx; x++) {
                    const uint8_t* p = rgba + ((size_t)y * w + x) * 4;
                    r += L[p[0]]; g += L[p[1]]; b += L[p[2]]; n++;
                    tr += p[0]; tg += p[1]; tb += p[2]; tn++;
                }
            linear_to_lab(r / n, g / n, b / n, feat + (sy * SUB + sx) * 3);
        }
    mean_rgb[0] = tr / tn; mean_rgb[1] = tg / tn; mean_rgb[2] = tb / tn;
}

// ---------------------------------------------------------------- 本体
struct Tile {
    std::vector<uint8_t> rgba;   // TILE x TILE
    double feat[FDIM];
    double mean[3];
};

struct Options {
    double reuse = 0.15;     // 使った回数 1 回ごとにコストを (1 + reuse) 倍
    int no_repeat = 2;       // この距離（マス）以内には同じタイルを置かない
    uint32_t seed = 1;       // マスを埋める順番の乱数
};

struct Mosaic {
    std::vector<Tile> tiles;
    std::vector<uint8_t> target;
    int tw = 0, th = 0;
    int cols = 0, rows = 0;
    std::vector<int> assign;            // rows*cols、タイル番号
    std::vector<double> cell_mean;      // rows*cols*3、マスの平均 RGB
    std::vector<int> uses;

    void add_tile(const uint8_t* rgba, int w, int h) {   // w == h == TILE を想定
        Tile t;
        t.rgba.assign(rgba, rgba + (size_t)w * h * 4);
        features(rgba, w, 0, 0, w, h, t.feat, t.mean);
        tiles.push_back(std::move(t));
    }

    void set_target(const uint8_t* rgba, int w, int h) {
        target.assign(rgba, rgba + (size_t)w * h * 4);
        tw = w; th = h;
    }

    // 横 cols マス。縦はマスが正方形になるように決める。
    bool build(int cols_, const Options& opt) {
        if (tiles.empty() || target.empty() || cols_ < 1) return false;
        cols = cols_;
        double cell = (double)tw / cols;
        rows = std::max(1, (int)std::floor(th / cell));
        double oy = (th - rows * cell) / 2;               // 余りは上下に振り分けて捨てる
        const int N = rows * cols, T = (int)tiles.size();
        std::vector<double> cf((size_t)N * FDIM);
        cell_mean.assign((size_t)N * 3, 0);
        for (int r = 0; r < rows; r++)
            for (int c = 0; c < cols; c++)
                features(target.data(), tw, c * cell, oy + r * cell, (c + 1) * cell, oy + (r + 1) * cell,
                         &cf[(size_t)(r * cols + c) * FDIM], &cell_mean[(size_t)(r * cols + c) * 3]);
        // 埋める順番を混ぜる（左上から順だと、右下ほど良いタイルが使い切られて偏る）
        std::vector<int> order(N);
        for (int i = 0; i < N; i++) order[i] = i;
        uint32_t s = opt.seed ? opt.seed : 1;
        for (int i = N - 1; i > 0; i--) {
            s = s * 1664525u + 1013904223u;
            int j = (int)((s >> 8) % (uint32_t)(i + 1));
            std::swap(order[i], order[j]);
        }
        assign.assign(N, -1);
        uses.assign(T, 0);
        std::vector<uint8_t> banned(T, 0);
        for (int idx : order) {
            int r = idx / cols, c = idx % cols;
            // 近くに置いたタイルは禁止
            std::vector<int> near;
            for (int dr = -opt.no_repeat; dr <= opt.no_repeat; dr++)
                for (int dc = -opt.no_repeat; dc <= opt.no_repeat; dc++) {
                    int rr = r + dr, cc = c + dc;
                    if (rr < 0 || cc < 0 || rr >= rows || cc >= cols) continue;
                    int a = assign[rr * cols + cc];
                    if (a >= 0 && !banned[a]) { banned[a] = 1; near.push_back(a); }
                }
            const double* f = &cf[(size_t)idx * FDIM];
            int best = -1; double bc = std::numeric_limits<double>::max();
            for (int pass = 0; pass < 2 && best < 0; pass++)     // タイルが少なくて全部禁止なら禁止を外す
                for (int t = 0; t < T; t++) {
                    if (pass == 0 && banned[t]) continue;
                    double d = 0;
                    const double* g = tiles[t].feat;
                    for (int k = 0; k < FDIM; k++) { double e = f[k] - g[k]; d += e * e; }
                    d *= 1.0 + opt.reuse * uses[t];
                    if (d < bc) { bc = d; best = t; }
                }
            for (int a : near) banned[a] = 0;
            assign[idx] = best;
            uses[best]++;
        }
        return true;
    }

    // 1 マス cell 画素で描いて out（(cols*cell) x (rows*cell) の RGBA）に書く。
    // blend: タイルの平均色をマスの平均色へ寄せる割合（0 = 写真そのまま）。
    void render(int cell, double blend, std::vector<uint8_t>& out) const {
        const int W = cols * cell, H = rows * cell;
        out.assign((size_t)W * H * 4, 255);
        for (int r = 0; r < rows; r++)
            for (int c = 0; c < cols; c++) {
                const Tile& t = tiles[assign[r * cols + c]];
                const double* cm = &cell_mean[(size_t)(r * cols + c) * 3];
                double sh[3];
                for (int k = 0; k < 3; k++) sh[k] = blend * (cm[k] - t.mean[k]);
                for (int y = 0; y < cell; y++) {
                    // タイル（TILE 画素）から cell 画素へ：画素中心で最近傍＋縮小時は小さな箱平均
                    int sy0 = y * TILE / cell, sy1 = std::max(sy0 + 1, (y + 1) * TILE / cell);
                    for (int x = 0; x < cell; x++) {
                        int sx0 = x * TILE / cell, sx1 = std::max(sx0 + 1, (x + 1) * TILE / cell);
                        double acc[3] = {0, 0, 0}; int n = 0;
                        for (int yy = sy0; yy < sy1; yy++)
                            for (int xx = sx0; xx < sx1; xx++) {
                                const uint8_t* p = &t.rgba[((size_t)yy * TILE + xx) * 4];
                                acc[0] += p[0]; acc[1] += p[1]; acc[2] += p[2]; n++;
                            }
                        uint8_t* o = &out[((size_t)(r * cell + y) * W + c * cell + x) * 4];
                        for (int k = 0; k < 3; k++) {
                            double v = acc[k] / n + sh[k];
                            o[k] = (uint8_t)std::min(255.0, std::max(0.0, std::round(v)));
                        }
                        o[3] = 255;
                    }
                }
            }
    }

    int distinct_used() const { int n = 0; for (int u : uses) n += u > 0; return n; }
};

}  // namespace photomosaic
