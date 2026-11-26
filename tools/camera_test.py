# PC のカメラ（getUserMedia）を Chromium の偽カメラで試す。iPhone を名乗ったときは従来どおり
# input[capture] のファイル選択に行くことも確かめる。
# usage: python tools/camera_test.py docs out_prefix
import sys, threading, http.server, functools
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root, pre = sys.argv[1], sys.argv[2]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8767), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:8767/index.html"
ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
    # --- PC
    ctx = b.new_context(viewport={"width": 1000, "height": 900}, permissions=["camera"])
    pg = ctx.new_page(); pg.on("console", lambda m: print("console:", m.text))
    chooser = []
    pg.on("filechooser", lambda fc: chooser.append(fc))
    pg.goto(URL)
    pg.click("text=カメラで撮る")
    pg.wait_for_function("document.getElementById('camVideo').videoWidth > 0", timeout=20000)
    pg.screenshot(path=pre + "_pc_cam.png")
    pg.click("#camShot")
    pg.wait_for_function("getComputedStyle(document.getElementById('targetPrev')).display === 'block'", timeout=20000)
    r1 = pg.evaluate("[document.getElementById('camBox').classList.contains('hidden'), document.getElementById('targetPrev').naturalWidth]")
    print("PC 元の写真: カメラ画面が閉じた=%s, プレビュー幅=%s, ファイル選択が開いた回数=%d" % (r1[0], r1[1], len(chooser)))
    ok &= r1[0] and r1[1] > 0 and not chooser
    pg.click("text=カメラで撮って追加")
    pg.wait_for_function("document.getElementById('camVideo').videoWidth > 0", timeout=20000)
    pg.click("#camShot"); pg.wait_for_timeout(800); pg.click("#camShot")
    pg.wait_for_function("document.getElementById('tileInfo').textContent.includes('タイル 2 枚')", timeout=20000)
    msg = pg.text_content("#camMsg"); pg.click("#camClose")
    print("PC タイル: %s / %s / ファイル選択=%d" % (msg, pg.text_content("#tileInfo"), len(chooser)))
    ok &= not chooser
    pg.screenshot(path=pre + "_pc_after.png", full_page=True)
    ctx.close()
    # --- iPhone を名乗る（従来どおりファイル選択に行くはず）
    ctx = b.new_context(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
                        viewport={"width": 390, "height": 844}, has_touch=True)
    pg = ctx.new_page()
    pg.goto(URL)
    with pg.expect_file_chooser(timeout=5000) as fc:
        pg.click("text=カメラで撮る")
    hidden = pg.evaluate("document.getElementById('camBox').classList.contains('hidden')")
    print("iPhone: ファイル選択が開いた=%s, 自前のカメラ画面は出ない=%s" % (fc.value is not None, hidden))
    ok &= hidden
    ctx.close()
    b.close()
srv.shutdown()
print("PASS" if ok else "FAIL")
