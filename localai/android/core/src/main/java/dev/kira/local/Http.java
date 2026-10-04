package dev.kira.local;

import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

/** Небольшая обёртка над HttpURLConnection с безопасной обработкой редиректов. */
final class Http {
    private Http() {}

    static final String UA = "KiraLocal/1.0";

    /** Открывает соединение, вручную проходя редиректы: заголовки авторизации не уходят на другие хосты. */
    static HttpURLConnection open(String url, Map<String, String> headers, long rangeStart) throws IOException {
        String current = url;
        String origHost = URI.create(url).getHost();
        for (int hop = 0; hop < 8; hop++) {
            URL u = new URL(current);
            if (!"http".equals(u.getProtocol()) && !"https".equals(u.getProtocol())) throw new IOException("Только http(s)");
            HttpURLConnection c = (HttpURLConnection) u.openConnection();
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(15000);
            c.setReadTimeout(60000);
            c.setRequestProperty("User-Agent", UA);
            boolean sameHost = origHost != null && origHost.equalsIgnoreCase(u.getHost());
            if (headers != null) {
                for (Map.Entry<String, String> e : headers.entrySet()) {
                    if (e.getKey().equalsIgnoreCase("Authorization") && !sameHost) continue;
                    c.setRequestProperty(e.getKey(), e.getValue());
                }
            }
            if (rangeStart > 0) c.setRequestProperty("Range", "bytes=" + rangeStart + "-");
            int code = c.getResponseCode();
            if (code >= 300 && code < 400 && c.getHeaderField("Location") != null) {
                current = new URL(u, c.getHeaderField("Location")).toString();
                c.disconnect();
                continue;
            }
            return c;
        }
        throw new IOException("Слишком много редиректов");
    }

    static byte[] readAll(InputStream in) throws IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        return out.toByteArray();
    }

    /** GET → JSON (объект или массив). Бросает HubException со статусом при ошибке. */
    static Object getJson(String url, Map<String, String> headers) throws IOException {
        HttpURLConnection c = open(url, headers, 0);
        try {
            int code = c.getResponseCode();
            if (code >= 400) throw new HubException(code, "HTTP " + code);
            String body = new String(readAll(c.getInputStream()), java.nio.charset.StandardCharsets.UTF_8);
            return new JSONTokener(body).nextValue();
        } finally {
            c.disconnect();
        }
    }

    static JSONObject obj(Object o) {
        return (JSONObject) o;
    }

    static JSONArray arr(Object o) {
        return (JSONArray) o;
    }

    static final class HubException extends IOException {
        final int status;

        HubException(int status, String msg) {
            super(msg);
            this.status = status;
        }
    }
}
