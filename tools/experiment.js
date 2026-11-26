// 設定を変えてモザイクを作る（tools/experiment.py から呼ぶ）。
//   node tools/experiment.js 設定.json
// 設定: {tiles: "build/x.raw", target: "build/y.raw", w, h, runs: [{name, cols, reuse, blend, lweight, cell}]}
const fs = require('fs');
require('../docs/photomosaic.js')().then(M => {
  const cfg = JSON.parse(fs.readFileSync(process.argv[2]));
  const T = M._pm_tile_size(), tiles = fs.readFileSync(cfg.tiles), n = tiles.length / (T * T * 4);
  const p = M._malloc(T * T * 4);
  for (let i = 0; i < n; i++) { M.HEAPU8.set(tiles.subarray(i * T * T * 4, (i + 1) * T * T * 4), p); M._pm_add_tile(p); }
  const raw = fs.readFileSync(cfg.target), q = M._malloc(raw.length);
  M.HEAPU8.set(raw, q); M._pm_set_target(q, cfg.w, cfg.h);
  for (const r of cfg.runs) {
    const t0 = Date.now();
    const rows = M._pm_build(r.cols, r.reuse, 2, 1, r.match_blend ?? r.blend, r.lweight);
    const o = M._pm_render(r.cell, r.blend);
    const ow = M._pm_out_w(), oh = M._pm_out_h();
    fs.writeFileSync(`build/exp_${r.name}.raw`, M.HEAPU8.subarray(o, o + ow * oh * 4));
    console.log(JSON.stringify({ name: r.name, w: ow, h: oh, rows, distinct: M._pm_distinct(), ms: Date.now() - t0 }));
  }
});
