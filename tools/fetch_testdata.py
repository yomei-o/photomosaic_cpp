# 試験用の写真を picsum.photos から取る（タイル 300 枚と元写真）。  python tools/fetch_testdata.py
import os, urllib.request, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(ROOT, "testdata", "tiles"), exist_ok=True)

def get(i):
    p = os.path.join(ROOT, "testdata", "tiles", f"{i:03d}.jpg")
    if not os.path.exists(p):
        urllib.request.urlretrieve(f"https://picsum.photos/seed/pm{i}/240/240", p)

with cf.ThreadPoolExecutor(8) as ex:
    list(ex.map(get, range(300)))
urllib.request.urlretrieve("https://picsum.photos/seed/target7/1200/900", os.path.join(ROOT, "testdata", "target.jpg"))
for s in (11, 23, 42):
    urllib.request.urlretrieve(f"https://picsum.photos/seed/color{s}/1200/900", os.path.join(ROOT, "testdata", f"target_{s}.jpg"))
print("ok")
