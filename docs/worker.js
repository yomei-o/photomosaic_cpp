// WASM を裏のスレッドで動かす。
//   {type:'tiles', data:[Uint8Array...]}   タイル（TILE x TILE の RGBA）を追加
//   {type:'reset'}                          タイルを全部捨てる
//   {type:'target', rgba, w, h}             元の写真
//   {type:'build', cols, reuse, cell, blend} 割り当てて描く
//   {type:'render', cell, blend}            割り当てはそのまま描き直す（色寄せだけ変えたとき）
importScripts('photomosaic.js');
let M = null, ntiles = 0;
const ready = PhotomosaicModule().then(m => { M = m; });

function render(cell, blend) {
  const t0 = performance.now();
  const p = M._pm_render(cell, blend);
  const w = M._pm_out_w(), h = M._pm_out_h();
  const rgba = new Uint8ClampedArray(M.HEAPU8.buffer.slice(p, p + w * h * 4));
  return { w, h, rgba, msRender: performance.now() - t0 };
}

onmessage = async (e) => {
  await ready;
  const d = e.data;
  if (d.type === 'reset') { M._pm_reset(); ntiles = 0; postMessage({ type: 'count', n: 0 }); }
  else if (d.type === 'tiles') {
    const T = M._pm_tile_size(), p = M._malloc(T * T * 4);
    for (const t of d.data) { M.HEAPU8.set(t, p); ntiles = M._pm_add_tile(p); }
    M._free(p);
    postMessage({ type: 'count', n: ntiles });
  } else if (d.type === 'target') {
    const p = M._malloc(d.rgba.length);
    M.HEAPU8.set(d.rgba, p); M._pm_set_target(p, d.w, d.h); M._free(p);
    postMessage({ type: 'target_ok' });
  } else if (d.type === 'build') {
    const t0 = performance.now();
    const rows = M._pm_build(d.cols, d.reuse, 2, 1 + Math.floor(Math.random() * 1e6));
    const msBuild = performance.now() - t0;
    if (!rows) { postMessage({ type: 'error', msg: 'タイルと元の写真の両方が必要です' }); return; }
    const r = render(d.cell, d.blend);
    postMessage({ type: 'done', rows, cols: d.cols, distinct: M._pm_distinct(), msBuild, ...r }, [r.rgba.buffer]);
  } else if (d.type === 'render') {
    const r = render(d.cell, d.blend);
    postMessage({ type: 'done', distinct: M._pm_distinct(), ...r }, [r.rgba.buffer]);
  }
};
