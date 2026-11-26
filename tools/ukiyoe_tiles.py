# 浮世絵の原画（build/ukiyoe_src/、tools/fetch_ukiyoe.py で集める）からタイルを切り出す。
# 浮世絵は 1 シリーズ数十枚しかないので、1 枚から大きさと位置を変えた正方形をたくさん切る。
#   from ukiyoe_tiles import make_tiles
#   tiles, src = make_tiles(series=("fuji", "tokaido"), scales=(1.0, 0.7, 0.5, 0.35))
#   tiles: (N, 64, 64, 3) uint8、src: 各タイルの元の原画の番号
import glob, json, math, os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "ukiyoe_src")
T = 64
TRIM = 0.035      # 外周の紙の余白を削る割合


def prints(series):
    cr = json.load(open(os.path.join(SRC, "credits.json"), encoding="utf-8"))
    return [c for c in cr if c["series"] in series]


def crops(w, h, scales, overlap=0.5):
    """短辺 × scale の正方形を、辺の (1-overlap) ずつずらして敷き詰める位置 (l, t, s)"""
    out = []
    for f in scales:
        s = min(w, h) * f
        step = s * (1 - overlap)
        nx = max(1, math.ceil((w - s) / step - 1e-6) + 1)
        ny = max(1, math.ceil((h - s) / step - 1e-6) + 1)
        for j in range(ny):
            for i in range(nx):
                l = 0 if nx == 1 else (w - s) * i / (nx - 1)
                t = 0 if ny == 1 else (h - s) * j / (ny - 1)
                out.append((l, t, s))
    return out


def make_tiles(series=("fuji", "tokaido", "edo"), scales=(1.0, 0.7, 0.5, 0.35), flip=False, trim=TRIM, overlap=0.5):
    tiles, src = [], []
    for k, c in enumerate(prints(series)):
        im = Image.open(os.path.join(SRC, c["file"])).convert("RGB")
        dx, dy = round(im.width * trim), round(im.height * trim)
        im = im.crop((dx, dy, im.width - dx, im.height - dy))
        for l, t, s in crops(im.width, im.height, scales, overlap):
            tile = im.resize((T, T), Image.LANCZOS, box=(l, t, l + s, t + s))
            tiles.append(np.asarray(tile)); src.append(k)
            if flip:
                tiles.append(np.asarray(tile)[:, ::-1]); src.append(k)
    return np.stack(tiles), np.array(src)


def atlas(tiles, cols=40):
    rows = math.ceil(len(tiles) / cols)
    a = np.zeros((rows * T, cols * T, 3), np.uint8)
    for i, t in enumerate(tiles):
        a[(i // cols) * T:(i // cols + 1) * T, (i % cols) * T:(i % cols + 1) * T] = t
    return Image.fromarray(a)
