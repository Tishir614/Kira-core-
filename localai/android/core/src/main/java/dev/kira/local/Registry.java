package dev.kira.local;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Библиотека установленных моделей (models.json). */
public final class Registry {
    public static final List<String> KINDS = Arrays.asList("chat", "code", "image", "other");
    private static final Pattern IMAGE = Pattern.compile("stable-diffusion|sdxl|sd[-_]?[0-9]|flux|diffusion|kandinsky");
    private static final Pattern CODE = Pattern.compile("coder|code|starcoder|codestral");
    private final File file;
    private final File modelsDir;

    public Registry(Config cfg) {
        this.file = new File(cfg.dataDir, "models.json");
        this.modelsDir = cfg.modelsDir;
    }

    public static String guessKind(String name, boolean hasModelIndex) {
        String low = name.toLowerCase();
        if (hasModelIndex || IMAGE.matcher(low).find()) return "image";
        if (CODE.matcher(low).find()) return "code";
        return "chat";
    }

    /** Один и тот же источник и набор файлов дают один и тот же id — поэтому работают докачка и проверка «уже установлена». */
    public static String stableId(String name, String key) {
        String s = name.replaceAll("[^a-zA-Z0-9._-]+", "-").replaceAll("^[-.]+|[-.]+$", "");
        if (s.length() > 50) s = s.substring(0, 50);
        if (s.isEmpty()) s = "model";
        try {
            byte[] d = java.security.MessageDigest.getInstance("SHA-1").digest(key.getBytes(StandardCharsets.UTF_8));
            StringBuilder h = new StringBuilder();
            for (int i = 0; i < 3; i++) h.append(String.format("%02x", d[i]));
            return s + "-" + h;
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public static String slugify(String name) {
        String s = name.replaceAll("[^a-zA-Z0-9._-]+", "-").replaceAll("^[-.]+|[-.]+$", "");
        if (s.length() > 60) s = s.substring(0, 60);
        if (s.isEmpty()) s = "model";
        return s + "-" + UUID.randomUUID().toString().substring(0, 6);
    }

    public synchronized JSONArray list() {
        try {
            if (!file.exists()) return new JSONArray();
            return new JSONArray(new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
        } catch (IOException | JSONException e) {
            return new JSONArray();
        }
    }

    public synchronized JSONObject get(String id) {
        JSONArray a = list();
        for (int i = 0; i < a.length(); i++) if (id.equals(a.getJSONObject(i).optString("id"))) return a.getJSONObject(i);
        return null;
    }

    private void write(JSONArray a) throws IOException {
        File tmp = new File(file.getPath() + ".tmp");
        Files.write(tmp.toPath(), a.toString(2).getBytes(StandardCharsets.UTF_8));
        Files.move(tmp.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING);
    }

    public synchronized JSONObject add(JSONObject entry) throws IOException {
        if (!KINDS.contains(entry.optString("kind"))) throw new IllegalArgumentException("kind: " + KINDS);
        entry.put("added", System.currentTimeMillis() / 1000);
        JSONArray a = list();
        a.put(entry);
        write(a);
        return entry;
    }

    public synchronized boolean remove(String id) throws IOException {
        JSONArray a = list(), kept = new JSONArray();
        for (int i = 0; i < a.length(); i++) if (!id.equals(a.getJSONObject(i).optString("id"))) kept.put(a.get(i));
        if (kept.length() == a.length()) return false;
        write(kept);
        deleteTree(new File(modelsDir, id));
        return true;
    }

    static void deleteTree(File f) {
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) deleteTree(k);
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }
}
