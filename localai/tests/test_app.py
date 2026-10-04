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
