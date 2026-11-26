// node tools/try_node.js 名前 cols cell blend  → build/名前_out.raw と .size
const fs = require('fs');
require('../docs/photomosaic.js')().then(M => {
  const [name, cols, cell, blend] = [process.argv[2], +process.argv[3], +process.argv[4], +process.argv[5]];
  const T = M._pm_tile_size(), tiles = fs.readFileSync('build/tiles.raw'), n = tiles.length / (T * T * 4);
  const p = M._malloc(T * T * 4);
  let t0 = Date.now();
  for (let i = 0; i < n; i++) { M.HEAPU8.set(tiles.subarray(i * T * T * 4, (i + 1) * T * T * 4), p); M._pm_add_tile(p); }
  const tAdd = Date.now() - t0;
  const [w, h] = fs.readFileSync(`build/${name}.size`, 'utf8').split(' ').map(Number);
  const raw = fs.readFileSync(`build/${name}.raw`), q = M._malloc(raw.length);
  M.HEAPU8.set(raw, q); M._pm_set_target(q, w, h);
  t0 = Date.now(); const rows = M._pm_build(cols, 0.15, 2, 1); const tBuild = Date.now() - t0;
  t0 = Date.now(); const o = M._pm_render(cell, blend); const tRender = Date.now() - t0;
  const ow = M._pm_out_w(), oh = M._pm_out_h();
  fs.writeFileSync(`build/${name}_out.raw`, M.HEAPU8.subarray(o, o + ow * oh * 4));
  fs.writeFileSync(`build/${name}_out.size`, `${ow} ${oh}`);
  console.log(`${name}: ${n} tiles, ${cols}x${rows} cells, distinct ${M._pm_distinct()}, out ${ow}x${oh}, add ${tAdd}ms build ${tBuild}ms render ${tRender}ms`);
});
