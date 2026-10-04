package dev.kira.local;

import fi.iki.elonen.NanoHTTPD;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONException;
import org.json.JSONObject;

/** Локальный HTTP-сервер: тот же REST-API, что у настольной версии (Python), поэтому интерфейс общий. */
public final class LocalServer extends NanoHTTPD {
    private final Config cfg;
    private final Registry registry;
    private final Hub hub;
    private final Downloads downloads;
    private final ModelRuntime runtime;

    public LocalServer(Config cfg, int port) {
        super("127.0.0.1", port);
        this.cfg = cfg;
        this.registry = new Registry(cfg);
        this.hub = new Hub(cfg);
        this.downloads = new Downloads(cfg, registry);
        this.runtime = new ModelRuntime(cfg, registry);
    }

    public void shutdown() {
        stop();
        runtime.shutdown();
    }

    private static Response json(Response.IStatus status, Object body) {
        return newFixedLengthResponse(status, "application/json; charset=utf-8", body.toString());
    }

    private static Response err(Response.IStatus status, String msg) {
        return json(status, new JSONObject().put("detail", msg));
    }

    private boolean authorized(IHTTPSession s) {
        if (cfg.token == null) return true;
        String cookie = s.getHeaders().get("cookie");
        if (cookie == null) return false;
        for (String part : cookie.split(";")) if (part.trim().equals("kt=" + cfg.token)) return true;
        return false;
    }

    @Override
    public Response serve(IHTTPSession s) {
        String uri = s.getUri();
        try {
            if (cfg.token != null && (uri.equals("/") || uri.equals("/index.html")) && cfg.token.equals(s.getParms().get("token"))) {
                Response r = asset("index.html");
                r.addHeader("Set-Cookie", "kt=" + cfg.token + "; Path=/; HttpOnly; SameSite=Strict");
                return r;
            }
            if (!authorized(s)) return err(Response.Status.FORBIDDEN, "Нет доступа");
            if (uri.startsWith("/api/")) return api(s, uri.substring(5));
            return asset(uri.equals("/") ? "index.html" : uri.substring(1));
        } catch (IllegalArgumentException e) {
            return err(Response.Status.BAD_REQUEST, e.getMessage());
        } catch (Http.HubException e) {
            return err(Response.Status.BAD_REQUEST, "Источник вернул ошибку: " + e.getMessage());
        } catch (Exception e) {
            return err(Response.Status.INTERNAL_ERROR, String.valueOf(e.getMessage()));
        }
    }

    private Response asset(String path) throws IOException {
        if (path.contains("..") || cfg.assets == null) return err(Response.Status.NOT_FOUND, "not found");
        InputStream in = cfg.assets.open(path);
        if (in == null) return err(Response.Status.NOT_FOUND, "not found");
        String type = path.endsWith(".html") ? "text/html; charset=utf-8" : path.endsWith(".js") ? "text/javascript" : path.endsWith(".css") ? "text/css" : path.endsWith(".svg") ? "image/svg+xml" : "application/octet-stream";
        return newChunkedResponse(Response.Status.OK, type, in);
    }

    private JSONObject body(IHTTPSession s) throws IOException, ResponseException {
        Map<String, String> files = new HashMap<>();
        s.parseBody(files);
        String raw = files.get("postData");
        try {
            return raw == null || raw.isEmpty() ? new JSONObject() : new JSONObject(raw);
        } catch (JSONException e) {
            throw new IllegalArgumentException("Некорректный JSON");
        }
    }

    private Response api(IHTTPSession s, String path) throws Exception {
        Method m = s.getMethod();
        Map<String, String> q = s.getParms();
        if (m == Method.GET && path.equals("status")) return json(Response.Status.OK, runtime.status());
        if (m == Method.GET && path.equals("models")) return json(Response.Status.OK, registry.list());
        if (m == Method.DELETE && path.startsWith("models/")) {
            String id = path.substring(7);
            runtime.unloadModel(id);
            return registry.remove(id) ? json(Response.Status.OK, new JSONObject().put("ok", true)) : err(Response.Status.NOT_FOUND, "Модель не найдена");
        }
        if (m == Method.POST && path.equals("models/external")) {
            JSONObject b = body(s);
            String kind = b.optString("kind", "chat"), url = b.optString("base_url");
            if (!(kind.equals("chat") || kind.equals("code"))) throw new IllegalArgumentException("kind: chat | code");
            if (!url.matches("^https?://.+")) throw new IllegalArgumentException("base_url должен начинаться с http(s)://");
            String name = b.optString("name", b.optString("remote_model", "external"));
            JSONObject e = new JSONObject().put("id", Registry.slugify(name)).put("name", name).put("kind", kind).put("format", "remote").put("base_url", url).put("source", "external");
            if (!b.optString("remote_model").isEmpty()) e.put("remote_model", b.getString("remote_model"));
            return json(Response.Status.OK, registry.add(e));
        }
        if (m == Method.GET && path.equals("hf/files")) return json(Response.Status.OK, hub.hfFiles(q.get("repo"), q.get("token")));
        if (m == Method.GET && path.equals("hf/search")) return json(Response.Status.OK, hub.hfSearch(q.get("q"), "1".equals(q.get("gguf"))));
        if (m == Method.GET && path.equals("github/assets")) return json(Response.Status.OK, hub.githubAssets(q.get("repo")));
        if (m == Method.POST && path.equals("downloads")) return json(Response.Status.OK, downloads.start(body(s)));
        if (m == Method.GET && path.equals("downloads")) return json(Response.Status.OK, downloads.list());
        if (m == Method.DELETE && path.startsWith("downloads/")) return json(Response.Status.OK, new JSONObject().put("ok", downloads.cancel(path.substring(10))));
        if (m == Method.POST && path.startsWith("slots/")) {
            String[] p = path.split("/");
            if (p.length == 3 && p[2].equals("load")) {
                JSONObject b = body(s);
                try {
                    runtime.load(p[1], b.optString("model_id"), b.optInt("ctx", 4096), b.optInt("gpu_layers", 0));
                } catch (ModelRuntime.RuntimeFailure e) {
                    return err(Response.Status.BAD_REQUEST, e.getMessage());
                }
                return json(Response.Status.OK, runtime.status());
            }
            if (p.length == 3 && p[2].equals("unload")) {
                if (runtime.slot(p[1]) == null) return err(Response.Status.NOT_FOUND, "slot");
                runtime.unload(p[1]);
                return json(Response.Status.OK, runtime.status());
            }
        }
        if (m == Method.POST && path.equals("chat")) return chat(body(s));
        if (m == Method.POST && path.equals("image")) return err(Response.Status.NOT_IMPLEMENTED, "Генерация изображений на устройстве пока не поддерживается. Используйте настольную версию или внешний сервер.");
        return err(Response.Status.NOT_FOUND, "Неизвестный метод");
    }

    /** Проксирует потоковый ответ llama-server / внешнего сервера как есть (SSE). */
    private Response chat(JSONObject req) throws IOException {
        ModelRuntime.Slot slot = runtime.slot(req.optString("slot", "chat"));
        if (slot == null || slot.baseUrl == null) return err(Response.Status.CONFLICT, "Модель не загружена. Откройте «Модели» и нажмите «Загрузить».");
        JSONObject body = new JSONObject().put("messages", req.optJSONArray("messages") == null ? new org.json.JSONArray() : req.getJSONArray("messages")).put("temperature", req.optDouble("temperature", 0.7)).put("stream", true);
        if (req.optInt("max_tokens", 0) > 0) body.put("max_tokens", req.getInt("max_tokens"));
        if (slot.modelName != null) body.put("model", slot.modelName);
        HttpURLConnection c = (HttpURLConnection) new URL(slot.baseUrl + "/chat/completions").openConnection();
        c.setConnectTimeout(10000);
        c.setReadTimeout(0);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        c.getOutputStream().write(body.toString().getBytes(StandardCharsets.UTF_8));
        int code = c.getResponseCode();
        if (code >= 400) {
            String detail = new String(Http.readAll(c.getErrorStream()), StandardCharsets.UTF_8);
            c.disconnect();
            String sse = "data: " + new JSONObject().put("error", detail.length() > 300 ? detail.substring(0, 300) : detail) + "\n\n";
            return newFixedLengthResponse(Response.Status.OK, "text/event-stream", new ByteArrayInputStream(sse.getBytes(StandardCharsets.UTF_8)), sse.length());
        }
        final HttpURLConnection conn = c;
        InputStream in = new java.io.FilterInputStream(c.getInputStream()) {
            @Override
            public void close() throws IOException {
                try {
                    super.close();
                } finally {
                    conn.disconnect();
                }
            }
        };
        Response r = newChunkedResponse(Response.Status.OK, "text/event-stream", in);
        r.addHeader("Cache-Control", "no-cache");
        return r;
    }
}
