import asyncio
import json

import httpx
import pytest

from kira_local.downloader import DownloadError, check_url, safe_relpath
from kira_local.registry import guess_kind
from kira_local.server import create_app

GGUF = b"GGUF" + b"x" * 5000


def hf_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/models/acme/tiny-GGUF":
        return httpx.Response(200, json={"siblings": [{"rfilename": "tiny.Q4_K_M.gguf", "size": len(GGUF)}]})
    if request.url.path == "/acme/tiny-GGUF/resolve/main/tiny.Q4_K_M.gguf":
        return httpx.Response(200, content=GGUF)
    if request.url.path == "/api/models":
        return httpx.Response(200, json=[{"id": "acme/tiny-GGUF", "downloads": 5, "likes": 1, "pipeline_tag": "text-generation"}])
    return httpx.Response(404)


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def test_safe_relpath_and_urls():
    for bad in ("../x", "/etc/passwd", "a/../../b", ""):
        with pytest.raises(DownloadError):
            safe_relpath(bad)
    assert str(safe_relpath("sub/model.gguf")) == "sub/model.gguf"
    with pytest.raises(DownloadError):
        check_url("file:///etc/passwd")
    with pytest.raises(DownloadError):
        check_url("https://evil.example/x", ("github.com",))
    check_url("https://objects.githubusercontent.com/x", ("githubusercontent.com",))


def test_guess_kind():
    assert guess_kind("Qwen2.5-Coder-7B") == "code"
    assert guess_kind("stable-diffusion-xl") == "image"
    assert guess_kind("Llama-3-8B") == "chat"


async def test_download_load_chat_flow(data_dir, fake_llama):
    app = create_app(transport=httpx.MockTransport(hf_handler))
    async with client(app) as c:
        assert (await c.get("/api/hf/files", params={"repo": "acme/tiny-GGUF"})).json() == [{"name": "tiny.Q4_K_M.gguf", "size": len(GGUF)}]
        assert (await c.get("/api/hf/search", params={"q": "tiny", "gguf": 1})).json()[0]["id"] == "acme/tiny-GGUF"
        job = (await c.post("/api/downloads", json={"source": "hf", "repo": "acme/tiny-GGUF", "files": ["tiny.Q4_K_M.gguf"]})).json()
        for _ in range(50):
            jobs = (await c.get("/api/downloads")).json()
            if jobs[0]["status"] in ("done", "error"):
                break
            await asyncio.sleep(0.1)
        assert jobs[0]["status"] == "done", jobs[0]
        models = (await c.get("/api/models")).json()
        assert models[0]["format"] == "gguf" and models[0]["kind"] == "chat"
        assert open(models[0]["path"], "rb").read() == GGUF

        r = await c.post("/api/chat", json={"slot": "chat", "messages": []})
        assert r.status_code == 409  # ещё не загружена

        r = await c.post("/api/slots/chat/load", json={"model_id": models[0]["id"]})
        assert r.status_code == 200, r.text
        r = await c.post("/api/chat", json={"slot": "chat", "messages": [{"role": "user", "content": "hi"}]})
        text = "".join(json.loads(l[5:])["choices"][0]["delta"]["content"] for l in r.text.splitlines() if l.startswith("data:") and "[DONE]" not in l)
        assert text == "Привет"

        assert (await c.post("/api/slots/chat/unload")).json()["slots"]["chat"]["model_id"] is None
        assert (await c.delete(f"/api/models/{models[0]['id']}")).status_code == 200
        assert (await c.get("/api/models")).json() == []


async def test_bad_requests(data_dir):
    app = create_app(transport=httpx.MockTransport(hf_handler))
    async with client(app) as c:
        assert (await c.post("/api/downloads", json={"source": "url", "urls": ["file:///etc/passwd"]})).status_code == 400
        assert (await c.post("/api/downloads", json={"source": "hf", "repo": "acme/tiny-GGUF", "files": ["../../evil"]})).status_code == 400
        assert (await c.post("/api/downloads", json={"source": "github", "urls": ["https://evil.example/a.gguf"]})).status_code == 400
        assert (await c.post("/api/slots/chat/load", json={"model_id": "nope"})).status_code == 400
        assert (await c.post("/api/image", json={"model_id": "nope", "prompt": "x"})).status_code == 400
        ext = await c.post("/api/models/external", json={"name": "ollama", "base_url": "http://localhost:11434/v1", "remote_model": "q"})
        assert ext.status_code == 200 and ext.json()["format"] == "remote"
        assert (await c.get("/")).status_code == 200
        for f in ("analyze.js", "hub.js", "app.js", "studio.js", "app.css"):
            assert (await c.get("/" + f)).status_code == 200, f
        assert (await c.get("/server.py")).status_code == 404


async def test_remote_image_flow_and_gallery(data_dir):
    import base64

    png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"images": [png]})

    real_client = httpx.Client

    class Patched(real_client):
        def __init__(self, *a, **k):
            k["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **k)

    import kira_local.imagegen as ig

    ig.httpx.Client = Patched
    try:
        app = create_app()
        async with client(app) as c:
            m = (await c.post("/api/models/external", json={"name": "A1111", "base_url": "http://pc:7860", "kind": "image", "api": "a1111"})).json()
            assert m["format"] == "remote_image"
            assert (await c.get("/api/status")).json()["images"] is True
            job = (await c.post("/api/image", json={"model_id": m["id"], "prompt": "cat", "steps": 5, "count": 2, "seed": 10})).json()
            for _ in range(50):
                st = (await c.get(f"/api/image/{job['id']}")).json()
                if st["status"] in ("done", "error"):
                    break
                await asyncio.sleep(0.1)
            assert st["status"] == "done", st
            assert [i["seed"] for i in st["images"]] == [10, 11] and calls[0]["seed"] == 10 and calls[0]["steps"] == 5
            assert (await c.get(st["images"][0]["url"])).content.startswith(b"\x89PNG")
            gal = (await c.get("/api/gallery")).json()
            assert len(gal) == 2 and gal[0]["prompt"] == "cat"
            assert (await c.delete(f"/api/gallery/{gal[0]['name']}")).json() == {"ok": True}
            assert (await c.delete("/api/gallery/..%2Fx.png")).status_code in (400, 404)
            assert len((await c.get("/api/gallery")).json()) == 1
    finally:
        ig.httpx.Client = real_client
