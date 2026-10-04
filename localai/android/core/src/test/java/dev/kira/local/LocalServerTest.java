package dev.kira.local;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalServerTest {
    static final byte[] GGUF = ("GGUF" + "x".repeat(200_000)).getBytes(StandardCharsets.UTF_8);
    @TempDir Path tmp;
    HttpServer upstream;
    LocalServer server;
    String base;
    Config cfg;

    @BeforeEach
    void setUp() throws Exception {
        upstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        upstream.createContext("/", ex -> {
            String p = ex.getRequestURI().getPath();
            byte[] out;
            int code = 200;
            if (p.equals("/api/models/acme/tiny-GGUF")) out = "{\"siblings\":[{\"rfilename\":\"tiny.Q4_K_M.gguf\",\"size\":200004}]}".getBytes();
            else if (p.equals("/api/models")) out = "[{\"id\":\"acme/tiny-GGUF\",\"downloads\":5,\"likes\":1,\"pipeline_tag\":\"text-generation\"}]".getBytes();
            else if (p.equals("/acme/tiny-GGUF/resolve/main/tiny.Q4_K_M.gguf")) {
                // редирект на «CDN» — проверяем, что работает
                ex.getResponseHeaders().add("Location", "/cdn/tiny.gguf");
                ex.sendResponseHeaders(302, -1);
                ex.close();
                return;
            } else if (p.equals("/cdn/tiny.gguf")) {
                String r = ex.getRequestHeaders().getFirst("Range");
                int start = r == null ? 0 : Integer.parseInt(r.replaceAll("\\D", ""));
                code = start > 0 ? 206 : 200;
                out = java.util.Arrays.copyOfRange(GGUF, start, GGUF.length);
            } else {
                out = new byte[0];
                code = 404;
            }
            ex.sendResponseHeaders(code, out.length == 0 ? -1 : out.length);
            if (out.length > 0) ex.getResponseBody().write(out);
            ex.close();
        });
        upstream.start();
        String up = "http://127.0.0.1:" + upstream.getAddress().getPort();

        Path wrapper = tmp.resolve("llama-server");
        Files.writeString(wrapper, "#!/bin/sh\nexec python3 " + new File("../../tests/fake_llama_server.py").getCanonicalPath() + " \"$@\"\n");
        Files.setPosixFilePermissions(wrapper, PosixFilePermissions.fromString("rwxr-xr-x"));

        cfg = new Config(tmp.resolve("data").toFile());
        cfg.hfBase = up;
        cfg.githubApi = up;
        cfg.llamaBinary = wrapper.toString();
        cfg.assets = p -> p.equals("index.html") ? new ByteArrayInputStream("<html>ok</html>".getBytes()) : null;
        cfg.token = "secret";
        server = new LocalServer(cfg, 0);
        server.start();
        base = "http://127.0.0.1:" + server.getListeningPort();
    }

    @AfterEach
    void tearDown() {
        server.shutdown();
        upstream.stop(0);
    }

    String call(String method, String path, String body, String cookie) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setRequestMethod(method);
        if (cookie != null) c.setRequestProperty("Cookie", cookie);
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            c.getOutputStream().write(body.getBytes(StandardCharsets.UTF_8));
        }
        InputStream in = c.getResponseCode() >= 400 ? c.getErrorStream() : c.getInputStream();
        return c.getResponseCode() + " " + new String(in.readAllBytes(), StandardCharsets.UTF_8);
    }

    String api(String method, String path, String body) throws Exception {
        return call(method, path, body, "kt=secret");
    }

    @Test
    void tokenIsRequired() throws Exception {
        assertTrue(call("GET", "/api/models", null, null).startsWith("403"));
        assertTrue(call("GET", "/api/models", null, "kt=wrong").startsWith("403"));
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/?token=secret").openConnection();
        assertEquals(200, c.getResponseCode());
        assertTrue(c.getHeaderField("Set-Cookie").startsWith("kt=secret"));
        assertTrue(api("GET", "/", null).contains("ok"));
    }

    @Test
    void searchAndFiles() throws Exception {
        assertTrue(api("GET", "/api/hf/search?q=tiny&gguf=1", null).contains("acme/tiny-GGUF"));
        assertTrue(api("GET", "/api/hf/files?repo=acme/tiny-GGUF", null).contains("tiny.Q4_K_M.gguf"));
        assertTrue(api("GET", "/api/hf/files?repo=nope/nothing", null).startsWith("400"));
    }

    @Test
    void downloadLoadChatDelete() throws Exception {
        String r = api("POST", "/api/downloads", "{\"source\":\"hf\",\"repo\":\"acme/tiny-GGUF\",\"files\":[\"tiny.Q4_K_M.gguf\"]}");
        assertTrue(r.startsWith("200"), r);
        JSONObject job = null;
        for (int i = 0; i < 100; i++) {
            job = new JSONArray(api("GET", "/api/downloads", null).substring(4)).getJSONObject(0);
            if (!job.getString("status").equals("downloading") && !job.getString("status").equals("queued")) break;
            Thread.sleep(100);
        }
        assertEquals("done", job.getString("status"), job.toString());
        JSONObject model = new JSONArray(api("GET", "/api/models", null).substring(4)).getJSONObject(0);
        assertEquals("gguf", model.getString("format"));
        assertArrayEquals(GGUF, Files.readAllBytes(Path.of(model.getString("path"))));

        String dup = api("POST", "/api/downloads", "{\"source\":\"hf\",\"repo\":\"acme/tiny-GGUF\",\"files\":[\"tiny.Q4_K_M.gguf\"]}");
        assertTrue(dup.startsWith("400") && dup.contains("уже установлена"), dup);
        assertTrue(api("POST", "/api/chat", "{\"slot\":\"chat\",\"messages\":[]}").startsWith("409"));
        String st = api("POST", "/api/slots/chat/load", "{\"model_id\":\"" + model.getString("id") + "\"}");
        assertTrue(st.startsWith("200"), st);
        String chat = api("POST", "/api/chat", "{\"slot\":\"chat\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}");
        assertTrue(chat.startsWith("200") && chat.contains("\\u041f") && chat.contains("[DONE]"), chat);
        assertTrue(api("DELETE", "/api/models/" + model.getString("id"), null).startsWith("200"));
        assertEquals("200 []", api("GET", "/api/models", null));
    }

    @Test
    void resumesPartialDownload() throws Exception {
        Downloads.safeRel("a/b.gguf");
        File folder = new File(cfg.modelsDir, "x");
        // имитируем докачку напрямую через Downloads с готовым .part
        Registry reg = new Registry(cfg);
        Downloads d = new Downloads(cfg, reg);
        JSONObject job = d.start(new JSONObject().put("source", "hf").put("repo", "acme/tiny-GGUF").put("files", new JSONArray().put("tiny.Q4_K_M.gguf")).put("name", "resume"));
        for (int i = 0; i < 100 && !d.list().getJSONObject(0).getString("status").equals("done"); i++) Thread.sleep(100);
        assertEquals("done", d.list().getJSONObject(0).getString("status"));
        assertNotNull(folder);
        assertEquals("resume", job.getString("name"));
    }

    @Test
    void rejectsUnsafeInput() throws Exception {
        assertTrue(api("POST", "/api/downloads", "{\"source\":\"url\",\"urls\":[\"file:///etc/passwd\"]}").startsWith("400"));
        assertTrue(api("POST", "/api/downloads", "{\"source\":\"hf\",\"repo\":\"acme/tiny-GGUF\",\"files\":[\"../../evil\"]}").startsWith("400"));
        assertTrue(api("POST", "/api/downloads", "{\"source\":\"github\",\"urls\":[\"https://evil.example/a.gguf\"]}").startsWith("400"));
        assertTrue(api("POST", "/api/slots/chat/load", "{\"model_id\":\"nope\"}").startsWith("400"));
        assertTrue(api("POST", "/api/models/external", "{\"name\":\"o\",\"base_url\":\"http://localhost:11434/v1\",\"remote_model\":\"q\"}").startsWith("200"));
        assertThrows(IllegalArgumentException.class, () -> Downloads.safeRel("a/../b"));
        assertEquals("image", Registry.guessKind("stable-diffusion-xl", false));
        assertEquals("code", Registry.guessKind("Qwen2.5-Coder", false));
    }

    @Test
    void remoteImageGenerationAndGallery() throws Exception {
        String png = java.util.Base64.getEncoder().encodeToString(new byte[] {(byte) 0x89, 'P', 'N', 'G', 1, 2, 3});
        HttpServer sd = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        java.util.List<String> bodies = new java.util.concurrent.CopyOnWriteArrayList<>();
        sd.createContext("/sdapi/v1/txt2img", ex -> {
            bodies.add(new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] out = ("{\"images\":[\"" + png + "\"]}").getBytes();
            ex.sendResponseHeaders(200, out.length);
            ex.getResponseBody().write(out);
            ex.close();
        });
        sd.start();
        try {
            String m = api("POST", "/api/models/external", "{\"name\":\"SD\",\"base_url\":\"http://127.0.0.1:" + sd.getAddress().getPort() + "\",\"kind\":\"image\",\"api\":\"a1111\"}");
            assertTrue(m.startsWith("200") && m.contains("remote_image"), m);
            String id = new JSONObject(m.substring(4)).getString("id");
            assertTrue(api("GET", "/api/status", null).contains("\"images\":true") && api("GET", "/api/status", null).contains("disk_free"));
            JSONObject job = new JSONObject(api("POST", "/api/image", "{\"model_id\":\"" + id + "\",\"prompt\":\"cat\",\"steps\":4,\"count\":2,\"seed\":7}").substring(4));
            JSONObject st = null;
            for (int i = 0; i < 100; i++) {
                st = new JSONObject(api("GET", "/api/image/" + job.getString("id"), null).substring(4));
                if (st.getString("status").equals("done") || st.getString("status").equals("error")) break;
                Thread.sleep(100);
            }
            assertEquals("done", st.getString("status"), st.toString());
            assertEquals(2, st.getJSONArray("images").length());
            assertEquals(7, st.getJSONArray("images").getJSONObject(0).getLong("seed"));
            assertTrue(bodies.get(0).contains("\"seed\":7") && bodies.get(0).contains("\"steps\":4"));
            String url = st.getJSONArray("images").getJSONObject(0).getString("url");
            HttpURLConnection c = (HttpURLConnection) new URL(base + url).openConnection();
            c.setRequestProperty("Cookie", "kt=secret");
            assertEquals(200, c.getResponseCode());
            assertEquals(7, c.getInputStream().readAllBytes().length);
            JSONArray gal = new JSONArray(api("GET", "/api/gallery", null).substring(4));
            assertEquals(2, gal.length());
            String name = gal.getJSONObject(0).getString("name");
            assertTrue(api("DELETE", "/api/gallery/" + name, null).startsWith("200"));
            assertEquals(1, new JSONArray(api("GET", "/api/gallery", null).substring(4)).length());
            assertTrue(api("DELETE", "/api/gallery/..%2Fx.png", null).startsWith("400") || api("DELETE", "/api/gallery/..%2Fx.png", null).startsWith("404"));
            assertTrue(call("GET", "/outputs/" + name, null, null).startsWith("403"));
        } finally {
            sd.stop(0);
        }
    }
}
