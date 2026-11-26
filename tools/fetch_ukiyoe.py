# 浮世絵（富嶽三十六景・東海道五十三次・名所江戸百景）をメトロポリタン美術館の Open Access（CC0）から集める。
#   python tools/fetch_ukiyoe.py [シリーズ...]      シリーズ: fuji tokaido edo（既定は全部）
# 原画は build/ukiyoe_src/ に置いておき（2 回目からは取りに行かない）、credits は build/ukiyoe_src/credits.json。
# isPublicDomain が true、作者がそのシリーズの絵師、題に「from the series ○○」があるものだけ使う。
import io, json, os, re, sys, time, urllib.request, urllib.parse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "build", "ukiyoe_src")
API = "https://collectionapi.metmuseum.org/public/collection/v1"
UA = {"User-Agent": "photomosaic_cpp sample fetcher"}
SERIES = {
    "fuji": ("Thirty-six Views of Mount Fuji", "Hokusai"),
    "tokaido": ("Fifty-three Stations of the T", "Hiroshige"),   # Tōkaidō / Tokaido の両方
    "edo": ("One Hundred Famous Views of Edo", "Hiroshige"),
}


def get(url, as_json=True):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r) if as_json else r.read()
        except Exception:
            time.sleep(5 * (i + 1))   # 速く叩くと 403 が返る
    return None


def norm_title(t):
    # 同じ絵の別の摺り（別の所蔵番号）をまとめるための題
    return re.sub(r"[^a-z]", "", t.split(", from the series")[0].lower())


def main():
    keys = sys.argv[1:] or list(SERIES)
    os.makedirs(SRC, exist_ok=True)
    cpath = os.path.join(SRC, "credits.json")
    credits = json.load(open(cpath, encoding="utf-8")) if os.path.exists(cpath) else []
    have = {c["objectID"] for c in credits}
    for key in keys:
        series, artist = SERIES[key]
        r = get(f"{API.replace('/v1', '/v1.1')}/search?hasImages=true&q={urllib.parse.quote(series)}&limit=500")
        ids = (r or {}).get("objectIDs") or []
        seen = {norm_title(c["title"]) for c in credits if c["series"] == key}
        got = 0
        for oid in ids:
            if oid in have:
                continue
            time.sleep(0.3)
            o = get(f"{API}/objects/{oid}")
            if not o or not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
                continue
            title = o.get("title", "")
            if artist not in o.get("artistDisplayName", "") or "from the series" not in title.lower() \
                    or series.lower() not in title.lower().replace("ō", "o").replace("tō", "to"):
                continue
            nt = norm_title(title)
            if nt in seen:          # 同じ絵は 1 枚だけ
                continue
            data = get(o["primaryImageSmall"], as_json=False)
            if not data:
                continue
            try:
                im = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue
            name = f"{key}_{oid}.jpg"
            im.save(os.path.join(SRC, name), quality=92)
            seen.add(nt)
            have.add(oid)
            credits.append({"objectID": oid, "series": key, "file": name, "title": title,
                            "artist": o.get("artistDisplayName", ""), "date": o.get("objectDate", ""),
                            "url": o.get("objectURL", ""), "image": o["primaryImageSmall"],
                            "license": "CC0 (The Met Open Access)"})
            got += 1
            print(f"{key} {got:3d} {im.size} {title[:80]}".encode("utf-8", "replace").decode("utf-8"), flush=True)
            json.dump(credits, open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(0.05)
        print(f"== {key}: +{got}, total {sum(c['series'] == key for c in credits)}")


if __name__ == "__main__":
    main()
