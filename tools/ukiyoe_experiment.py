# 浮世絵タイルでどこまで写真を描けるかを測る。
#   python tools/ukiyoe_experiment.py [横マス数]
# タイルの集め方（原画 1 枚 = 1 タイル / 大きさと位置を変えて切り出す）と色寄せを変えて、
# 名画タイル 300 枚（docs/samples/tiles.jpg）と比べる。近さは experiment.py と同じ ΔE。
# 並べた画像は build/uk_sheet_*.jpg。
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from experiment import to_lab, NODE, ROOT
from ukiyoe_tiles import make_tiles, T

B = os.path.join(ROOT, "build")


def write_tiles(name, tiles):
    rgba = np.concatenate([tiles, np.full(tiles.shape[:3] + (1,), 255, np.uint8)], -1)
    open(os.path.join(B, f"uk_tiles_{name}.raw"), "wb").write(rgba.tobytes())
    return f"build/uk_tiles_{name}.raw"


def met_tiles():
    a = np.asarray(Image.open(os.path.join(ROOT, "docs", "samples", "tiles.jpg")).convert("RGB"))
    return np.stack([a[r * T:(r + 1) * T, c * T:(c + 1) * T] for r in range(a.shape[0] // T) for c in range(a.shape[1] // T)])


def score(mos, im, cols, rows):
    sw, sh = cols * 2, rows * 2
    cell = im.width / cols
    oy = (im.height - rows * cell) / 2
    ref = im.crop((0, round(oy), im.width, round(oy + rows * cell)))
    L1 = to_lab(np.asarray(mos.resize((sw, sh), Image.BOX), np.float64))
    L2 = to_lab(np.asarray(ref.resize((sw, sh), Image.BOX), np.float64))
    return np.sqrt(((L1 - L2) ** 2).sum(-1)).mean(), np.abs(L1[..., 0] - L2[..., 0]).mean()


def main():
    cols = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    os.makedirs(B, exist_ok=True)
    # 2026-11-26 の 1 回目: 原画 1 枚 = 1 タイル（214 枚）は名画 300 枚より全部悪い。切り出し（6165 枚）は 5 枚中 3 枚で良い
    # 2 回目: 明るさを分けて寄せる（Lab、明るさ 70%・色み 20%）と暗い絵で ΔE 20.1 → 10.4
    # 3 回目: 同じ原画を近くに置かない（組）と、隣が同じ原画の割合 22〜43% → 0%、ΔE は 1〜2 悪化。見た目は組ありが良い
    # 4 回目: ブラウザの重さのため枚数を減らす
    sets = {}
    for name, sc, ov in [("uk65", (1.0, 0.7, 0.5, 0.35), 0.5), ("uk44", (1.0, 0.7, 0.5, 0.35), 0.33),
                         ("uk34", (1.0, 0.6, 0.4), 0.33)]:
        sets[name] = make_tiles(trim=0.06, scales=sc, overlap=ov)
    make_groups = {}
    for k, (v, g) in sets.items():
        print(f"tiles {k}: {len(v)}")
    sets_path = {}
    for k, (v, g) in sets.items():
        sets_path[k] = write_tiles(k, v)
        if g is not None:
            json.dump([int(x) for x in g], open(os.path.join(B, f"uk_groups_{k}.json"), "w"))
    targets = [os.path.join(ROOT, "docs", "samples", f"target_{i}.jpg") for i in (1, 2, 3)] + \
              [os.path.join(ROOT, "testdata", f"target_{i}.jpg") for i in (23, 42)]
    # (名前, 色みの寄せ, 明るさの寄せ)。明るさが負 = 従来の sRGB で一緒に寄せる
    confs = [("c20_l70", 0.2, 0.7)]
    font = ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc", 14)
    table = {}
    for tp in targets:
        tn = os.path.splitext(os.path.basename(tp))[0]
        im = ImageOps.exif_transpose(Image.open(tp)).convert("RGB")
        sc = min(1.0, 1600 / max(im.size))
        im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
        tg = np.asarray(im.convert("RGBA"))
        open(os.path.join(B, "uk_target.raw"), "wb").write(tg.tobytes())
        imgs = []
        for sk, spath in sets_path.items():
            runs = [{"name": f"uk_{sk}_{cn}", "cols": cols, "reuse": 0.05, "blend": b, "lblend": lb, "lweight": 2.0, "cell": 24}
                    for cn, b, lb in confs]
            cfg = {"tiles": spath, "target": "build/uk_target.raw", "w": tg.shape[1], "h": tg.shape[0], "runs": runs}
            if sets[sk][1] is not None:
                cfg["groups"] = f"build/uk_groups_{sk}.json"
            json.dump(cfg, open(os.path.join(B, "uk_cfg.json"), "w"))
            out = subprocess.run([NODE, "tools/experiment.js", "build/uk_cfg.json"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout
            for r, (b, _, _) in zip([json.loads(l) for l in out.splitlines() if l.startswith("{")], confs):
                a = np.frombuffer(open(os.path.join(B, f"exp_{r['name']}.raw"), "rb").read(), np.uint8)
                mos = Image.fromarray(a.reshape(r["h"], r["w"], 4)[..., :3])
                de, dl = score(mos, im, cols, r["rows"])
                # 隣（上下左右）が同じ原画になっている割合。原画の分からない met300 はタイル同士
                asg = np.array(json.load(open(os.path.join(B, f"exp_{r['name']}.assign.json")))).reshape(r["rows"], cols)
                grp = sets[sk][1] if sets[sk][1] is not None else (make_groups[sk] if sk in make_groups else None)
                gg = grp[asg] if grp is not None else asg
                same = ((gg[:, 1:] == gg[:, :-1]).sum() + (gg[1:] == gg[:-1]).sum()) / (gg[:, 1:].size + gg[1:].size)
                table[(tn, sk, b)] = (de, dl, r["distinct"], same)
                imgs.append((sk, b, de, mos))
                mos.save(os.path.join(B, f"uk_{tn}_{sk}_{b}.jpg"), quality=90)
        # 並べた画像：行 = タイルの集め方、列 = 元写真＋色寄せ
        tw = 360
        th = round(imgs[0][3].height * tw / imgs[0][3].width)
        n = len(sets)
        sheet = Image.new("RGB", (tw * (1 + len(confs)), (th + 22) * n), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        sheet.paste(im.resize((tw, round(im.height * tw / im.width))).crop((0, 0, tw, th)), (0, 22))
        d.text((4, 2), "元の写真", fill=(0, 0, 0), font=font)
        for i, (sk, b, de, mos) in enumerate(imgs):
            x, y = tw * (1 + i % len(confs)), (th + 22) * (i // len(confs))
            sheet.paste(mos.resize((tw, th), Image.LANCZOS), (x, y + 22))
            d.text((x + 4, y + 2), f"{sk}（{len(sets[sk][0])} 枚） {b}  ΔE {de:.1f}", fill=(0, 0, 0), font=font)
        sheet.save(os.path.join(B, f"uk_sheet_{tn}.jpg"), quality=88)
    print(f"\ncols {cols}   ΔE（明るさのずれ） 使った種類")
    tns = sorted({k[0] for k in table}, key=lambda s: [os.path.splitext(os.path.basename(t))[0] for t in targets].index(s))
    for sk in sets:
        for b, _, _ in confs:
            cells = [f"{table[(tn, sk, b)][0]:5.2f}({table[(tn, sk, b)][1]:4.1f}) {table[(tn, sk, b)][2]:4d} {table[(tn, sk, b)][3] * 100:4.1f}%" for tn in tns]
            print(f"{sk:8s} {b:8s} " + " | ".join(cells))
    print("targets:", ", ".join(tns))


if __name__ == "__main__":
    main()
