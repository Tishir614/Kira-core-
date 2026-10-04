package dev.kira.local;

import java.io.IOException;
import java.net.URLEncoder;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/** Каталоги источников: Hugging Face (поиск, список файлов) и GitHub releases. */
public final class Hub {
    static final Pattern REPO = Pattern.compile("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$");
    private final Config cfg;

    public Hub(Config cfg) {
        this.cfg = cfg;
    }

    static Map<String, String> auth(String token) {
        Map<String, String> h = new HashMap<>();
        if (token != null && !token.isEmpty()) h.put("Authorization", "Bearer " + token);
        return h;
    }

    static String enc(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8");
        } catch (java.io.UnsupportedEncodingException e) {
            throw new IllegalStateException(e);
        }
    }

    public JSONArray hfFiles(String repo, String token) throws IOException {
        if (repo == null || !REPO.matcher(repo).matches()) throw new IllegalArgumentException("Ожидается repo вида owner/name");
        JSONArray out = new JSONArray();
        try {
            JSONObject o = Http.obj(Http.getJson(cfg.hfBase + "/api/models/" + repo + "?blobs=true", auth(token)));
            JSONArray sib = o.optJSONArray("siblings");
            if (sib != null) {
                for (int i = 0; i < sib.length(); i++) {
                    JSONObject s = sib.getJSONObject(i);
                    out.put(new JSONObject().put("name", s.getString("rfilename")).put("size", s.optLong("size", 0)));
                }
            }
        } catch (Http.HubException e) {
            if (e.status == 404 || e.status == 401) throw new IllegalArgumentException("Репозиторий не найден (или нужен токен)");
            throw e;
        }
        return out;
    }

    public JSONArray hfSearch(String query, boolean ggufOnly) throws IOException {
        String url = cfg.hfBase + "/api/models?sort=downloads&direction=-1&limit=20&search=" + enc(query == null ? "" : query) + (ggufOnly ? "&filter=gguf" : "");
        JSONArray src = Http.arr(Http.getJson(url, null)), out = new JSONArray();
        for (int i = 0; i < src.length(); i++) {
            JSONObject m = src.getJSONObject(i);
            out.put(new JSONObject().put("id", m.optString("id", m.optString("modelId"))).put("downloads", m.optLong("downloads")).put("likes", m.optLong("likes")).put("task", m.optString("pipeline_tag", "")));
        }
        return out;
    }

    public JSONArray githubAssets(String repo) throws IOException {
        if (repo == null || !REPO.matcher(repo).matches()) throw new IllegalArgumentException("Ожидается repo вида owner/name");
        JSONArray out = new JSONArray();
        try {
            JSONArray rels = Http.arr(Http.getJson(cfg.githubApi + "/repos/" + repo + "/releases?per_page=5", null));
            for (int i = 0; i < rels.length(); i++) {
                JSONObject rel = rels.getJSONObject(i);
                JSONArray assets = rel.optJSONArray("assets");
                if (assets == null) continue;
                for (int j = 0; j < assets.length(); j++) {
                    JSONObject a = assets.getJSONObject(j);
                    out.put(new JSONObject().put("name", a.getString("name")).put("size", a.optLong("size")).put("url", a.getString("browser_download_url")).put("tag", rel.optString("tag_name")));
                }
            }
        } catch (Http.HubException e) {
            if (e.status == 404) throw new IllegalArgumentException("Репозиторий или релизы не найдены");
            throw e;
        }
        return out;
    }
}
