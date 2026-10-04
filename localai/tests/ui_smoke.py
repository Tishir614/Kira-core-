"""Дымовой UI-тест в headless Chromium (ручной запуск):  python tests/ui_smoke.py http://127.0.0.1:8772
Проходит все экраны, подменяет Hugging Face / GitHub и падает при любой JS-ошибке."""
import glob
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
GB = 1e9
INFO = {"pipeline_tag": "text-generation", "tags": ["gguf"], "downloads": 10, "likes": 2, "cardData": {"license": "mit"}, "gguf": {"total": 1.5e9, "architecture": "qwen2", "context_length": 32768},
        "siblings": [{"rfilename": "m-q4_k_m.gguf", "size": 1 * GB}, {"rfilename": "m-q8_0.gguf", "size": 1.6 * GB}]}
H = {"access-control-allow-origin": "*"}


def jr(r, body):
    r.fulfill(status=200, headers=H, content_type="application/json", body=json.dumps(body))


def hf(r):
    u = r.request.url
    if "whoami" in u:
        jr(r, {"name": "bob", "fullname": "Bob", "avatarUrl": ""})
    elif "/likes" in u:
        jr(r, [])
    elif "/api/models/" in u:
        jr(r, INFO)
    elif "/api/models" in u:
        jr(r, [{"id": "acme/tiny-GGUF", "downloads": 5, "likes": 1, "pipeline_tag": "text-generation", "tags": ["gguf"]}])
    elif u.endswith("README.md"):
        r.fulfill(status=200, headers=H, body="Tiny model")
    else:
        r.abort()


def gh(r):
    u = r.request.url
    if "rate_limit" in u:
        jr(r, {"resources": {"core": {"remaining": 59, "limit": 60}}})
    elif "search/repositories" in u:
        jr(r, {"items": [{"full_name": "o/r", "name": "r", "description": "d", "stargazers_count": 1, "owner": {"login": "o"}}]})
    elif u.endswith("/user"):
        jr(r, {"login": "al", "name": "Al", "avatar_url": ""})
    else:
        jr(r, [])


def main():
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome") or [None])[0])
        pg = b.new_page(viewport={"width": 390, "height": 800})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.route("https://huggingface.co/**", hf)
        pg.route("https://api.github.com/**", gh)
        pg.goto(BASE)
        pg.wait_for_selector("#v-onboard.active")
        for _ in range(3):
            pg.click("#obNext")
        pg.wait_for_selector("#v-connect.active")
        pg.click("#acctDone")
        pg.wait_for_selector("#v-home.active")
        assert "Стартовый набор" in pg.inner_text("#homeBody"), "стартовый набор должен быть виден без моделей"
        for view in ["chat", "code", "image", "duel", "library", "connect", "home"]:
            pg.evaluate(f"go('{view}',{{root:true}})")
            pg.wait_for_selector(f"#v-{view}.active")
        # поиск → карточка → назад
        pg.fill("#homeQ", "tiny")
        pg.press("#homeQ", "Enter")
        pg.wait_for_selector("#searchRes .cardx")
        pg.click("#searchRes .cardx >> nth=0")
        pg.wait_for_selector("#detailBody .opt")
        assert pg.evaluate("kiraBack()") is True and pg.evaluate("current") == "search"
        # ссылка в строке поиска
        pg.evaluate("go('home',{root:true})")
        pg.fill("#homeQ", "https://huggingface.co/acme/tiny-GGUF")
        pg.press("#homeQ", "Enter")
        pg.wait_for_selector("#detailBody .opt")
        # чат без модели: сообщение не теряется, текст возвращается в поле
        pg.evaluate("go('chat',{root:true})")
        pg.fill("#chatInput", "привет")
        pg.click("#chatSend")
        pg.wait_for_selector("#v-library.active")
        assert pg.evaluate("chat().messages.length") == 0
        assert pg.input_value("#chatInput") == "привет"
        # диагностика
        pg.click("text=Проверить приложение и сеть")
        pg.wait_for_selector("#lightbox:not(.hidden) .cardx >> nth=6")
        assert "Hugging Face" in pg.inner_text("#lightbox")
        pg.evaluate("kiraBack()")
        # меню
        pg.evaluate("openMenu()")
        assert pg.locator("#menu button.mi").count() >= 7
        pg.evaluate("closeMenu()")
        b.close()
    assert not errors, errors
    print("UI smoke OK")


main()
