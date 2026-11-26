# デモ用に、浮世絵の原画（build/ukiyoe_src/、tools/fetch_ukiyoe.py で集める）を 1 枚の画像にまとめる。
#   python tools/pack_ukiyoe.py
# 出力（docs/samples/）:
#   ukiyoe.jpg    余白を削った原画を長辺 LONG 画素に縮めて棚詰めしたもの
#   ukiyoe.json   各原画の位置（x, y, w, h）と作品名・作者・所蔵ページ、ブラウザで切り出すときの設定
# タイルはブラウザで切り出す（index.html の ukiyoeCrops。tools/ukiyoe_tiles.py の crops と同じ並び）。
# 64x64 のタイル 4000 枚を画像で持つより軽い。
import json, os, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ukiyoe_tiles import prints, SRC, ROOT

OUT = os.path.join(ROOT, "docs", "samples")
LONG = 320          # 一番小さい切り出し（短辺の 35%）がタイル 64 画素より大きくなるように
WIDTH = 2048
TRIM = 0.06         # 外周の紙の余白を削る割合（ukiyoe_experiment.py の 3 回目）
CROP = {"scales": [1.0, 0.7, 0.5, 0.35], "overlap": 0.33}


def main():
    ps = prints(("fuji", "tokaido", "edo"))
    ims = []
    for c in ps:
        im = Image.open(os.path.join(SRC, c["file"])).convert("RGB")
        dx, dy = round(im.width * TRIM), round(im.height * TRIM)
        im = im.crop((dx, dy, im.width - dx, im.height - dy))
        sc = LONG / max(im.size)
        ims.append(im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS))
    # 高さの順に棚へ詰める
    order = sorted(range(len(ims)), key=lambda i: -ims[i].height)
    x = y = shelf = 0
    pos = [None] * len(ims)
    for i in order:
        w, h = ims[i].size
        if x + w > WIDTH:
            x, y, shelf = 0, y + shelf, 0
        pos[i] = (x, y)
        x += w; shelf = max(shelf, h)
    atlas = Image.new("RGB", (WIDTH, y + shelf), (0, 0, 0))
    for im, (x, y) in zip(ims, pos):
        atlas.paste(im, (x, y))
    atlas.save(os.path.join(OUT, "ukiyoe.jpg"), quality=86)
    meta = {"crop": CROP, "trim": TRIM, "license": "CC0 (The Met Open Access)", "prints": [
        {"x": p[0], "y": p[1], "w": im.width, "h": im.height, "series": c["series"], "title": c["title"],
         "artist": c["artist"], "date": c["date"], "url": c["url"]} for c, im, p in zip(ps, ims, pos)]}
    with open(os.path.join(OUT, "ukiyoe.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=1)
    kb = os.path.getsize(os.path.join(OUT, "ukiyoe.jpg")) // 1024
    print(f"{len(ps)} prints -> ukiyoe.jpg {atlas.size} {kb} KB")


if __name__ == "__main__":
    main()
