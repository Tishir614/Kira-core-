package dev.kira.local;

import java.io.File;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.URL;
import org.json.JSONObject;

/** Слоты «chat» и «code»: каждый — свой процесс llama-server либо внешний OpenAI-совместимый сервер. */
public final class ModelRuntime {
    public static final class Slot {
        volatile String modelId, baseUrl, modelName;
        volatile boolean loading;
        Process proc;
    }

    public static final class RuntimeFailure extends Exception {
        public RuntimeFailure(String m) {
            super(m);
        }
    }

    private final Config cfg;
    private final Registry registry;
    public final Slot chat = new Slot(), code = new Slot();

    public ModelRuntime(Config cfg, Registry registry) {
        this.cfg = cfg;
        this.registry = registry;
    }

    public Slot slot(String name) {
        if ("chat".equals(name)) return chat;
        if ("code".equals(name)) return code;
        return null;
    }

    public JSONObject status() {
        return new JSONObject().put("llama_server", cfg.llamaBinary == null ? JSONObject.NULL : cfg.llamaBinary).put("platform", cfg.platform).put("images", cfg.images).put("diffusers", cfg.images)
                .put("slots", new JSONObject().put("chat", pub(chat)).put("code", pub(code)));
    }

    private static JSONObject pub(Slot s) {
        return new JSONObject().put("model_id", s.modelId == null ? JSONObject.NULL : s.modelId).put("loading", s.loading);
    }

    public void load(String slotName, String modelId, int ctx, int gpuLayers) throws RuntimeFailure {
        Slot slot = slot(slotName);
        if (slot == null) throw new RuntimeFailure("slot: chat | code");
        JSONObject m = registry.get(modelId);
        if (m == null) throw new RuntimeFailure("Модель не найдена");
        String kind = m.optString("kind");
        if (kind.equals("image")) throw new RuntimeFailure("Модель изображений используется во вкладке «Изображения»");
        if (kind.equals("other")) throw new RuntimeFailure("Тип «other» только хранится; запускать можно chat/code модели");
        synchronized (slot) {
            if (slot.loading) throw new RuntimeFailure("Слот уже загружается");
            unload(slotName);
            slot.loading = true;
        }
        try {
            String fmt = m.optString("format");
            if (fmt.equals("remote")) {
                slot.baseUrl = m.getString("base_url").replaceAll("/+$", "");
                slot.modelName = m.optString("remote_model", null);
            } else if (fmt.equals("gguf")) {
                startLlama(slot, m, ctx, gpuLayers);
            } else {
                throw new RuntimeFailure("Формат «" + fmt + "» нельзя запустить для чата. Нужен GGUF (или подключите внешний сервер).");
            }
            slot.modelId = modelId;
        } catch (RuntimeFailure | RuntimeException e) {
            unload(slotName); // не оставляем «полузагруженный» слот с чужим адресом
            throw e;
        } finally {
            slot.loading = false;
        }
    }

    private static int freePort() throws IOException {
        try (ServerSocket s = new ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) {
            return s.getLocalPort();
        }
    }

    private void startLlama(Slot slot, JSONObject m, int ctx, int ngl) throws RuntimeFailure {
        if (cfg.llamaBinary == null) throw new RuntimeFailure("llama-server не найден. На ПК установите llama.cpp (https://github.com/ggml-org/llama.cpp/releases) и задайте LLAMA_SERVER_BIN.");
        try {
            int port = freePort();
            File log = new File(cfg.dataDir, "llama-" + port + ".log");
            ProcessBuilder pb = new ProcessBuilder(cfg.llamaBinary, "-m", m.getString("path"), "--host", "127.0.0.1", "--port", String.valueOf(port), "-c", String.valueOf(ctx), "-ngl", String.valueOf(ngl), "-t", String.valueOf(cfg.threads));
            pb.redirectErrorStream(true).redirectOutput(log);
            slot.proc = pb.start();
            slot.baseUrl = "http://127.0.0.1:" + port + "/v1";
            slot.modelName = null;
            long deadline = System.currentTimeMillis() + 300_000;
            while (System.currentTimeMillis() < deadline) {
                if (!slot.proc.isAlive()) {
                    stop(slot);
                    throw new RuntimeFailure("llama-server завершился (лог: " + log.getName() + "). Возможно, не хватает памяти.");
                }
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:" + port + "/health").openConnection();
                    c.setConnectTimeout(1000);
                    c.setReadTimeout(2000);
                    int code = c.getResponseCode();
                    c.disconnect();
                    if (code == 200) return;
                } catch (IOException ignored) {
                    // сервер ещё стартует
                }
                Thread.sleep(500);
            }
            stop(slot);
            throw new RuntimeFailure("Таймаут запуска модели");
        } catch (IOException e) {
            throw new RuntimeFailure("Не удалось запустить llama-server: " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            stop(slot);
            throw new RuntimeFailure("Прервано");
        }
    }

    private static void stop(Slot s) {
        if (s.proc != null) {
            s.proc.destroy();
            try {
                if (!s.proc.waitFor(10, java.util.concurrent.TimeUnit.SECONDS)) s.proc.destroyForcibly();
            } catch (InterruptedException e) {
                s.proc.destroyForcibly();
                Thread.currentThread().interrupt();
            }
            s.proc = null;
        }
    }

    public void unload(String name) {
        Slot s = slot(name);
        if (s == null) return;
        stop(s);
        s.modelId = s.baseUrl = s.modelName = null;
    }

    public void unloadModel(String modelId) {
        if (modelId.equals(chat.modelId)) unload("chat");
        if (modelId.equals(code.modelId)) unload("code");
    }

    public void shutdown() {
        unload("chat");
        unload("code");
    }
}
