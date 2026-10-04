package dev.kira.local.app;

import android.content.Context;
import dev.kira.local.Config;
import dev.kira.local.LocalServer;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.security.SecureRandom;

/** Единственный экземпляр локального сервера на процесс. */
final class ServerHolder {
    private static LocalServer server;
    static String token;

    private ServerHolder() {}

    static synchronized int ensure(Context ctx) throws IOException {
        if (server != null && server.isAlive()) return server.getListeningPort();
        Context app = ctx.getApplicationContext();
        File base = app.getExternalFilesDir(null);
        if (base == null) base = app.getFilesDir();
        Config cfg = new Config(base);
        File bin = new File(app.getApplicationInfo().nativeLibraryDir, "libllama_server.so");
        cfg.llamaBinary = bin.exists() ? bin.getPath() : null;
        cfg.platform = "android";
        cfg.images = false;
        cfg.threads = Math.max(2, Runtime.getRuntime().availableProcessors() - 2);
        byte[] raw = new byte[16];
        new SecureRandom().nextBytes(raw);
        StringBuilder sb = new StringBuilder();
        for (byte b : raw) sb.append(String.format("%02x", b));
        token = sb.toString();
        cfg.token = token;
        cfg.assets = path -> {
            try {
                return app.getAssets().open("web/" + path);
            } catch (FileNotFoundException e) {
                return null;
            }
        };
        server = new LocalServer(cfg, 0);
        server.start();
        return server.getListeningPort();
    }

    static synchronized void stop() {
        if (server != null) {
            server.shutdown();
            server = null;
        }
    }
}
