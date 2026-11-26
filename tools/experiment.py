# 照合のしかたと色寄せを変えて、元の写真にどれだけ近いかを測る。
#   python tools/experiment.py [元写真] [横マス数]
# 近さ: モザイクと元写真をどちらも 横 2×マス数 に縮小し、Lab の色差 ΔE76 を平均（小さいほど近い）。
# 比べる組み合わせの画像を build/exp_sheet.jpg に並べる。
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.environ.get("NODE", r"C:\prog\emsdk\emsdk\node\22.16.0_64bit\bin\node.exe")
T = 64


def to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "samples", "target_1.jpg")
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    atlas = np.asarray(Image.open(os.path.join(ROOT, "docs", "samples", "tiles.jpg")).convert("RGBA"))
    tiles = [atlas[r * T:(r + 1) * T, c * T:(c + 1) * T] for r in range(atlas.shape[0] // T) for c in range(atlas.shape[1] // T)]
    open(os.path.join(ROOT, "build", "exp_tiles.raw"), "wb").write(np.stack(tiles).tobytes())
    im = ImageOps.exif_transpose(Image.open(target)).convert("RGB")   # iPhone の写真は向きが EXIF にある
    tg = np.asarray(im.convert("RGBA"))
    open(os.path.join(ROOT, "build", "exp_target.raw"), "wb").write(tg.tobytes())
    runs = []
    for blend in (0.0, 0.25, 0.4):
        runs.append({"name": f"old_b{int(blend*100)}", "cols": cols, "reuse": 0.15, "blend": blend,
                     "match_blend": 0.0, "lweight": 1.0, "cell": 24})
        runs.append({"name": f"new_b{int(blend*100)}", "cols": cols, "reuse": 0.15, "blend": blend,
                     "match_blend": blend, "lweight": 2.0, "cell": 24})
    cfg = {"tiles": "build/exp_tiles.raw", "target": "build/exp_target.raw", "w": tg.shape[1], "h": tg.shape[0], "runs": runs}
    cpath = os.path.join(ROOT, "build", "exp_cfg.json")
    json.dump(cfg, open(cpath, "w"))
    out = subprocess.run([NODE, "tools/experiment.js", cpath], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    res = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    print(f"target {os.path.basename(target)}  cols {cols}  tiles {len(tiles)}")
    print(f"{'name':10s} {'ΔE':>6s} {'ΔE(明るさのみ)':>14s} {'種類':>5s}")
    imgs = []
    for r in res:
        a = np.frombuffer(open(os.path.join(ROOT, "build", f"exp_{r['name']}.raw"), "rb").read(), np.uint8)
        a = a.reshape(r["h"], r["w"], 4)[..., :3]
        mos = Image.fromarray(a)
        rows = r["rows"]
        sw, sh = cols * 2, rows * 2
        # 元写真もモザイクと同じ範囲（余りは上下に振り分けて捨てる）で比べる
        cell = im.width / cols
        oy = (im.height - rows * cell) / 2
        ref = im.crop((0, round(oy), im.width, round(oy + rows * cell)))
        L1 = to_lab(np.asarray(mos.resize((sw, sh), Image.BOX), np.float64))
        L2 = to_lab(np.asarray(ref.resize((sw, sh), Image.BOX), np.float64))
        de = np.sqrt(((L1 - L2) ** 2).sum(-1)).mean()
        dl = np.abs(L1[..., 0] - L2[..., 0]).mean()
        print(f"{r['name']:10s} {de:6.2f} {dl:14.2f} {r['distinct']:5d}")
        imgs.append((r["name"], de, mos))
    # 並べた画像（上段: 今の照合、下段: 新しい照合、左から色寄せ 0/25/40%）
    tw = 420
    th = round(imgs[0][2].height * tw / imgs[0][2].width)
    sheet = Image.new("RGB", (tw * 4, th * 2 + 40), (255, 255, 255))
    refimg = im.resize((tw, round(im.height * tw / im.width)))
    sheet.paste(refimg.crop((0, 0, tw, min(th, refimg.height))), (0, 20))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\meiryo.ttc", 14)
    d.text((4, 2), "元の写真", fill=(0, 0, 0), font=font)
    order = ["old_b0", "old_b25", "old_b40", "new_b0", "new_b25", "new_b40"]
    for k, name in enumerate(order):
        n, de, mos = next(x for x in imgs if x[0] == name)
        x = tw * (1 + k % 3)
        y = 20 + (th + 20) * (k // 3)
        sheet.paste(mos.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x + 4, y - 18), f"{'今の照合' if name.startswith('old') else '新しい照合'} 色寄せ {name.split('_b')[1]}%  ΔE {de:.1f}", fill=(0, 0, 0), font=font)
    sheet.save(os.path.join(ROOT, "build", "exp_sheet.jpg"), quality=90)


if __name__ == "__main__":
    main()
