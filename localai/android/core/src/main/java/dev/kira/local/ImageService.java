package dev.kira.local;

import java.io.File;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Random;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/** Генерация изображений через внешний сервер (A1111/Forge или OpenAI-совместимый) + галерея. Те же эндпоинты, что в Python-версии. */
public final class ImageService {
    static final Pattern NAME = Pattern.compile("^[A-Za-z0-9_.-]+\\.png$");

    static final class Job {
        final String id = UUID.randomUUID().toString().substring(0, 10);
        final JSONObject params;
        volatile String status = "queued", error;
        volatile int step;
        final int total;
        final JSONArray images = new JSONArray();
        volatile boolean cancel;

        Job(JSONObject params) {
            this.params = params;
            this.total = params.getInt("steps") * params.getInt("count");
        }

        JSONObject toJson() {
            synchronized (images) {
                return new JSONObject().put("id", id).put("status", status).put("step", step).put("total", total).put("images", new JSONArray(images.toString())).put("error", error == null ? JSONObject.NULL : error);
            }
        }
    }

    private final Config cfg;
    private final Map<String, Job> jobs = new LinkedHashMap<>();
    private final ExecutorService pool = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "kira-image");
        t.setDaemon(true);
        return t;
    });

    public ImageService(Config cfg) {
        this.cfg = cfg;
    }

    private static int clamp(int v, int lo, int hi, String name) {
        if (v < lo || v > hi) throw new IllegalArgumentException(name + ": " + lo + ".." + hi);
        return v;
    }

    public synchronized JSONObject submit(JSONObject model, JSONObject req) {
        if (!"remote_image".equals(model.optString("format")))
            throw new IllegalStateException("Локальная генерация на телефоне пока недоступна. Подключите внешний сервер (A1111/Forge/ComfyUI-совместимый, OpenAI API) во вкладке «Свой сервер».");
        String prompt = req.optString("prompt").trim();
        if (prompt.isEmpty()) throw new IllegalArgumentException("Пустой промпт");
        JSONObject p = new JSONObject().put("prompt", prompt).put("negative", req.optString("negative", ""))
                .put("steps", clamp(req.optInt("steps", 25), 1, 150, "steps")).put("width", clamp(req.optInt("width", 512), 64, 2048, "width")).put("height", clamp(req.optInt("height", 512), 64, 2048, "height"))
                .put("guidance", req.optDouble("guidance", 7.0)).put("count", clamp(req.optInt("count", 1), 1, 4, "count"))
                .put("seed", req.has("seed") && !req.isNull("seed") ? req.getLong("seed") : (long) new Random().nextInt(Integer.MAX_VALUE));
        Job job = new Job(p);
        jobs.put(job.id, job);
        while (jobs.size() > 30) jobs.remove(jobs.keySet().iterator().next());
        pool.execute(() -> run(job, model));
        return job.toJson();
    }

    public synchronized JSONObject status(String id) {
        Job j = jobs.get(id);
        return j == null ? null : j.toJson();
    }

    public synchronized boolean cancel(String id) {
        Job j = jobs.get(id);
        if (j == null) return false;
        j.cancel = true;
        return true;
    }

    private void run(Job job, JSONObject model) {
        job.status = "running";
        try {
            int count = job.params.getInt("count");
            for (int i = 0; i < count && !job.cancel; i++) {
                long seed = (job.params.getLong("seed") + i) % Integer.MAX_VALUE;
                byte[] png = remote(model, job.params, seed);
                JSONObject meta = new JSONObject();
                for (String k : new String[] {"prompt", "negative", "steps", "width", "height", "guidance"}) meta.put(k, job.params.get(k));
                meta.put("seed", seed).put("model", model.optString("name"));
                synchronized (job.images) {
                    job.images.put(save(png, meta));
                }
                job.step = (i + 1) * job.params.getInt("steps");
            }
            job.status = job.cancel ? "cancelled" : "done";
        } catch (Exception e) {
            job.error = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            job.status = "error";
        }
    }

    private byte[] remote(JSONObject model, JSONObject p, long seed) throws IOException {
        String base = model.getString("base_url").replaceAll("/+$", "");
        boolean openai = "openai".equals(model.optString("api"));
        String url;
        JSONObject body;
        if (openai) {
            url = base + "/images/generations";
            body = new JSONObject().put("model", model.optString("remote_model", "default")).put("prompt", p.getString("prompt")).put("n", 1)
                    .put("size", p.getInt("width") + "x" + p.getInt("height")).put("response_format", "b64_json");
        } else {
            url = base.replaceAll("/(v1|sdapi/v1)$", "") + "/sdapi/v1/txt2img";
            body = new JSONObject().put("prompt", p.getString("prompt")).put("negative_prompt", p.getString("negative")).put("steps", p.getInt("steps")).put("width", p.getInt("width"))
                    .put("height", p.getInt("height")).put("seed", seed).put("cfg_scale", p.getDouble("guidance")).put("batch_size", 1);
        }
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(600000);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        c.getOutputStream().write(body.toString().getBytes(StandardCharsets.UTF_8));
        try {
            int code = c.getResponseCode();
            if (code >= 400) throw new IOException("Сервер изображений ответил " + code);
            JSONObject r = new JSONObject(new String(Http.readAll(c.getInputStream()), StandardCharsets.UTF_8));
            String b64 = openai ? r.getJSONArray("data").getJSONObject(0).getString("b64_json") : r.getJSONArray("images").getString(0);
            int comma = b64.indexOf(',');
            return Base64.getDecoder().decode(comma >= 0 ? b64.substring(comma + 1) : b64);
        } finally {
            c.disconnect();
        }
    }

    private JSONObject save(byte[] png, JSONObject meta) throws IOException {
        String name = (System.currentTimeMillis() / 1000) + "-" + UUID.randomUUID().toString().substring(0, 6) + ".png";
        Files.write(new File(cfg.outputsDir, name).toPath(), png);
        meta.put("name", name).put("url", "/outputs/" + name).put("created", System.currentTimeMillis() / 1000);
        Files.write(new File(cfg.outputsDir, name.replace(".png", ".json")).toPath(), meta.toString().getBytes(StandardCharsets.UTF_8));
        return meta;
    }

    public JSONArray gallery(int limit) {
        File[] files = cfg.outputsDir.listFiles((d, n) -> n.endsWith(".png"));
        JSONArray out = new JSONArray();
        if (files == null) return out;
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        for (File f : new ArrayList<>(Arrays.asList(files)).subList(0, Math.min(limit, files.length))) {
            JSONObject meta = new JSONObject();
            File side = new File(cfg.outputsDir, f.getName().replace(".png", ".json"));
            try {
                if (side.exists()) meta = new JSONObject(new String(Files.readAllBytes(side.toPath()), StandardCharsets.UTF_8));
            } catch (Exception ignored) {
                // повреждённый sidecar — показываем без параметров
            }
            out.put(meta.put("name", f.getName()).put("url", "/outputs/" + f.getName()));
        }
        return out;
    }

    public boolean delete(String name) {
        if (!NAME.matcher(name).matches()) throw new IllegalArgumentException("Недопустимое имя файла");
        File f = new File(cfg.outputsDir, name);
        if (!f.exists()) return false;
        //noinspection ResultOfMethodCallIgnored
        f.delete();
        //noinspection ResultOfMethodCallIgnored
        new File(cfg.outputsDir, name.replace(".png", ".json")).delete();
        return true;
    }

    public File file(String name) {
        if (!NAME.matcher(name).matches()) return null;
        File f = new File(cfg.outputsDir, name);
        return f.isFile() ? f : null;
    }
}
