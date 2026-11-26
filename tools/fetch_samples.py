# デモと試験用のサンプル画像を、メトロポリタン美術館の Open Access（CC0）から集める。
#   python tools/fetch_samples.py
# 出力（docs/samples/）:
#   tiles.jpg      タイル 300 枚を 64x64 に中央切り抜きして 20x15 に並べたもの（1280x960）
#   target_*.jpg   元写真のサンプル（肖像画、長辺 1200）
#   credits.json   各画像の作品名・作者・所蔵ページ・ライセンス
# isPublicDomain が true の作品だけ使う（Met の Open Access = CC0）。
import io, json, os, sys, time, urllib.request, urllib.parse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "samples")
API = "https://collectionapi.metmuseum.org/public/collection/v1"
UA = {"User-Agent": "photomosaic_cpp sample fetcher"}
T, COLS, ROWS = 64, 20, 15
N_TILES = COLS * ROWS

# 色と題材がばらけるように、いろいろな言葉で探す
TILE_QUERIES = ["landscape", "flowers", "still life", "sea", "ukiyo-e", "garden", "bird", "textile",
                "ceramic", "kimono", "mountain", "river", "autumn", "snow", "sunset", "city", "horse",
                "fruit", "butterfly", "glass", "fan", "screen", "tapestry", "boat", "tree"]
TARGET_QUERIES = [("portrait", "Self-Portrait with a Straw Hat"), ("portrait", "Madame X"),
                  ("portrait", "Juan de Pareja")]


def get_json(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(1 + i)
    return None


def get_image(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def search(q, limit=80):
    # /v1/search は 2026-10-01 に廃止。/v1.1/search は offset と limit でページ分け
    j = get_json(f"{API.replace('/v1', '/v1.1')}/search?hasImages=true&q={urllib.parse.quote(q)}&limit={limit}")
    if j is None:
        sys.exit(f"search failed: {q}")
    return j.get("objectIDs") or []


def obj(oid):
    o = get_json(f"{API}/objects/{oid}")
    if not o or not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
        return None
    return o


def credit(o):
    return {"objectID": o["objectID"], "title": o.get("title", ""), "artist": o.get("artistDisplayName", ""),
            "date": o.get("objectDate", ""), "url": o.get("objectURL", ""),
            "image": o.get("primaryImageSmall", ""), "license": "CC0 (The Met Open Access)"}


def square_tile(im):
    s = min(im.size)
    l, t = (im.width - s) // 2, (im.height - s) // 2
    im = im.crop((l, t, l + s, t + s))
    while im.width > 2 * T:
        im = im.resize((max(T, im.width // 2),) * 2, Image.BOX)
    return im.resize((T, T), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    credits = {"tiles": [], "targets": []}
    # 元写真（肖像画）：題名で探して最初の Public Domain を使う
    for q, title in TARGET_QUERIES:
        for oid in search(title)[:15]:
            o = obj(oid)
            if o and title.lower() in o.get("title", "").lower():
                im = get_image(o["primaryImageSmall"])
                sc = min(1.0, 1200 / max(im.size))
                im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
                name = f"target_{len(credits['targets']) + 1}.jpg"
                im.save(os.path.join(OUT, name), quality=88)
                c = credit(o); c["file"] = name
                credits["targets"].append(c)
                print("target", name, o["title"], "/", o.get("artistDisplayName"))
                break
    # タイル：言葉ごとに少しずつ取って 300 枚
    per = N_TILES // len(TILE_QUERIES) + 2
    seen, tiles = set(), []
    for q in TILE_QUERIES:
        got = 0
        for oid in search(q):
            if len(tiles) >= N_TILES or got >= per:
                break
            if oid in seen:
                continue
            seen.add(oid)
            o = obj(oid)
            if not o:
                continue
            try:
                tiles.append(square_tile(get_image(o["primaryImageSmall"])))
            except Exception:
                continue
            credits["tiles"].append(credit(o))
            got += 1
            time.sleep(0.05)
        print(f"{q}: {got}  (total {len(tiles)})")
        if len(tiles) >= N_TILES:
            break
    if len(tiles) < N_TILES:
        print("tiles not enough:", len(tiles)); sys.exit(1)
    atlas = Image.new("RGB", (COLS * T, ROWS * T))
    for i, t in enumerate(tiles[:N_TILES]):
        atlas.paste(t, ((i % COLS) * T, (i // COLS) * T))
    atlas.save(os.path.join(OUT, "tiles.jpg"), quality=90)
    credits["tiles"] = credits["tiles"][:N_TILES]
    credits["tile_layout"] = {"tile": T, "cols": COLS, "rows": ROWS, "order": "row-major"}
    with open(os.path.join(OUT, "credits.json"), "w", encoding="utf-8") as fp:
        json.dump(credits, fp, ensure_ascii=False, indent=1)
    print("done", len(credits["tiles"]), "tiles,", len(credits["targets"]), "targets")


if __name__ == "__main__":
    main()
