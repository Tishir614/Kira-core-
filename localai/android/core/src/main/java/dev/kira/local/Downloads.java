package dev.kira.local;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONArray;
import org.json.JSONObject;

/** Фоновые загрузки моделей с докачкой, прогрессом и отменой. */
public final class Downloads {
    static final class FileState {
        final String name;
        final String url;
        final File dest;
        volatile long done, total;

        FileState(String name, String url, File dest) {
            this.name = name;
            this.url = url;
            this.dest = dest;
        }
    }

    static final class Job {
        final String id = UUID.randomUUID().toString().substring(0, 10);
        String modelId, name, kind, source;
        volatile String status = "queued", error;
        final List<FileState> files = new ArrayList<>();
        volatile boolean cancelled;
        volatile HttpURLConnection conn;

        JSONObject toJson() {
            long done = 0, total = 0;
            JSONArray fs = new JSONArray();
            for (FileState f : files) {
                done += f.done;
                total += f.total;
                fs.put(new JSONObject().put("name", f.name).put("done", f.done).put("total", f.total));
            }
            return new JSONObject().put("id", id).put("model_id", modelId).put("name", name).put("kind", kind).put("source", source).put("status", status).put("error", error == null ? JSONObject.NULL : error).put("files", fs).put("done", done).put("total", total);
        }
    }

    private final Config cfg;
    private final Registry registry;
    private final Map<String, Job> jobs = new LinkedHashMap<>();
    private final ExecutorService pool = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "kira-download");
        t.setDaemon(true);
        return t;
    });

    public Downloads(Config cfg, Registry registry) {
        this.cfg = cfg;
        this.registry = registry;
    }

    /** Относительный путь внутри папки модели: без «..», абсолютных путей и пустых частей. */
    static String safeRel(String name) {
        String n = name == null ? "" : name.replace('\\', '/');
        if (n.isEmpty() || n.startsWith("/")) throw new IllegalArgumentException("Недопустимый путь файла: " + name);
        for (String part : n.split("/", -1)) if (part.isEmpty() || part.equals("..") || part.equals(".")) throw new IllegalArgumentException("Недопустимый путь файла: " + name);
        return n;
    }

    static void checkUrl(String url, String allowedHost) {
        URI u;
        try {
            u = URI.create(url);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Некорректная ссылка");
        }
        String scheme = u.getScheme();
        if (u.getHost() == null || scheme == null || !(scheme.equals("http") || scheme.equals("https"))) throw new IllegalArgumentException("Разрешены только http(s) ссылки");
        if (allowedHost != null) {
            String h = u.getHost();
            boolean ok = h.equals(allowedHost) || h.endsWith("." + allowedHost) || h.endsWith(".githubusercontent.com");
            if (!ok) throw new IllegalArgumentException("Хост " + h + " не разрешён для этого источника");
        }
    }

    public synchronized JSONArray list() {
        JSONArray a = new JSONArray();
        for (Job j : jobs.values()) a.put(j.toJson());
        return a;
    }

    public JSONObject start(JSONObject req) {
        String source = req.optString("source");
        String kind = req.optString("kind", "");
        String name = req.optString("name", "");
        String repo = req.optString("repo", "");
        String token = req.optString("hf_token", "");
        if (token.isEmpty()) token = System.getenv("HF_TOKEN") == null ? "" : System.getenv("HF_TOKEN");
        Job job = new Job();
        job.source = source;
        job.modelId = Registry.slugify(name.isEmpty() ? (repo.isEmpty() ? "model" : repo.substring(repo.indexOf('/') + 1)) : name);
        File folder = new File(cfg.modelsDir, job.modelId);
        Map<String, String> headers = new HashMap<>();
        boolean hasIndex = false;
        List<String> rels = new ArrayList<>();
        JSONArray files = req.optJSONArray("files"), urls = req.optJSONArray("urls");
        switch (source) {
            case "hf": {
                if (!Hub.REPO.matcher(repo).matches() || files == null || files.length() == 0) throw new IllegalArgumentException("Для Hugging Face нужны repo и список файлов");
                headers.putAll(Hub.auth(token));
                for (int i = 0; i < files.length(); i++) {
                    String rel = safeRel(files.getString(i));
                    rels.add(rel);
                    job.files.add(new FileState(rel, cfg.hfBase + "/" + repo + "/resolve/main/" + rel, new File(folder, rel)));
                    if (rel.endsWith("model_index.json")) hasIndex = true;
                }
                job.name = name.isEmpty() ? repo.substring(repo.indexOf('/') + 1) : name;
                break;
            }
            case "github":
            case "url": {
                if (urls == null || urls.length() == 0) throw new IllegalArgumentException("Нужна хотя бы одна ссылка");
                for (int i = 0; i < urls.length(); i++) {
                    String u = urls.getString(i);
                    checkUrl(u, source.equals("github") ? cfg.githubAllowedHost : null);
                    String path = URI.create(u).getPath();
                    String fname = path.substring(path.lastIndexOf('/') + 1);
                    String rel = safeRel(fname);
                    rels.add(rel);
                    job.files.add(new FileState(rel, u, new File(folder, rel)));
                }
                job.name = name.isEmpty() ? (repo.isEmpty() ? rels.get(0) : repo.substring(repo.indexOf('/') + 1)) : name;
                break;
            }
            default:
                throw new IllegalArgumentException("source: hf | github | url");
        }
        if (!kind.isEmpty() && !Registry.KINDS.contains(kind)) throw new IllegalArgumentException("kind: " + Registry.KINDS);
        job.kind = kind.isEmpty() ? Registry.guessKind(job.name + " " + String.join(" ", rels), hasIndex) : kind;
        synchronized (this) {
            jobs.put(job.id, job);
        }
        final Job j = job;
        pool.execute(() -> run(j, folder, rels, headers));
        return job.toJson();
    }

    public boolean cancel(String id) {
        Job j;
        synchronized (this) {
            j = jobs.get(id);
        }
        if (j == null || !(j.status.equals("downloading") || j.status.equals("queued"))) return false;
        j.cancelled = true;
        HttpURLConnection c = j.conn;
        if (c != null) c.disconnect();
        return true;
    }

    private void run(Job job, File folder, List<String> rels, Map<String, String> headers) {
        job.status = "downloading";
        try {
            for (FileState f : job.files) {
                //noinspection ResultOfMethodCallIgnored
                f.dest.getParentFile().mkdirs();
                fetch(job, f, headers);
            }
            File main = mainPath(folder, rels);
            long total = 0;
            for (FileState f : job.files) total += f.done;
            boolean diffusers = new File(folder, "model_index.json").exists();
            String fn = main.getName();
            String fmt = diffusers ? "diffusers" : fn.contains(".") ? fn.substring(fn.lastIndexOf('.') + 1).toLowerCase() : "file";
            registry.add(new JSONObject().put("id", job.modelId).put("name", job.name).put("kind", job.kind).put("format", fmt).put("path", main.getPath()).put("source", job.source).put("size", total));
            job.status = "done";
        } catch (Exception e) {
            if (job.cancelled) {
                job.status = "cancelled";
            } else {
                job.error = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                job.status = "error";
            }
        }
    }

    static File mainPath(File folder, List<String> rels) {
        if (new File(folder, "model_index.json").exists()) return folder;
        for (String ext : new String[] {".gguf", ".safetensors", ".onnx", ".ckpt", ".bin"})
            for (String r : rels) if (r.toLowerCase().endsWith(ext)) return new File(folder, r);
        return new File(folder, rels.get(0));
    }

    private void fetch(Job job, FileState f, Map<String, String> headers) throws IOException {
        File part = new File(f.dest.getPath() + ".part");
        long start = part.exists() ? part.length() : 0;
        HttpURLConnection c = Http.open(f.url, headers, start);
        job.conn = c;
        try {
            int code = c.getResponseCode();
            if (code == 416) {
                Files.move(part.toPath(), f.dest.toPath(), StandardCopyOption.REPLACE_EXISTING);
                f.done = f.total = f.dest.length();
                return;
            }
            if (code == 401 || code == 403) throw new IOException("Доступ запрещён — нужен токен Hugging Face (gated-модель)");
            if (code >= 400) throw new IOException("HTTP " + code);
            if (start > 0 && code != 206) start = 0;
            long len = c.getContentLengthLong();
            f.total = len > 0 ? start + len : 0;
            f.done = start;
            try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(part, start > 0)) {
                byte[] buf = new byte[1 << 16];
                int n;
                while ((n = in.read(buf)) > 0) {
                    if (job.cancelled) throw new IOException("cancelled");
                    out.write(buf, 0, n);
                    f.done += n;
                }
            }
            if (f.total == 0) f.total = f.done;
            Files.move(part.toPath(), f.dest.toPath(), StandardCopyOption.REPLACE_EXISTING);
        } finally {
            c.disconnect();
        }
    }
}
