package dev.kira.local;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;

/** Настройки ядра. Одинаковы для Android и JVM (тесты). */
public final class Config {
    /** Источник статических файлов интерфейса (assets на Android). */
    public interface AssetSource {
        /** @return поток файла или null, если файла нет */
        InputStream open(String path) throws IOException;
    }

    public File dataDir;
    public File modelsDir;
    /** Путь к исполняемому llama-server (или null). */
    public String llamaBinary;
    public AssetSource assets;
    /** Если задан — запросы без cookie с этим токеном отклоняются. */
    public String token;
    public int threads = Math.max(1, Runtime.getRuntime().availableProcessors() / 2);
    public String hfBase = "https://huggingface.co";
    public String githubApi = "https://api.github.com";
    public String githubAllowedHost = "github.com";
    public String platform = "jvm";
    public boolean images = false;

    public Config(File dataDir) {
        this.dataDir = dataDir;
        this.modelsDir = new File(dataDir, "models");
        //noinspection ResultOfMethodCallIgnored
        modelsDir.mkdirs();
    }
}
