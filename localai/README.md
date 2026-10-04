# Kira Local

Локальное приложение для работы с ИИ-моделями на вашем компьютере.

1. **Модели** (левая шторка) — скачивайте модели с Hugging Face, из GitHub Releases или по прямой ссылке; можно подключить свой сервер (Ollama, LM Studio).
2. **Чат** — основной экран; работает с загруженной текстовой моделью (GGUF через `llama-server`), ответы стримятся.
3. **Студия** (правая шторка) — вкладка **Код** (отдельная code-модель со своим слотом) и вкладка **Изображения** (генерация через diffusers).

## Запуск

```bash
pip install -r requirements.txt
python -m kira_local            # http://127.0.0.1:8765
```

- Для GGUF-моделей нужен [llama.cpp](https://github.com/ggml-org/llama.cpp/releases): `llama-server` в `PATH` или `LLAMA_SERVER_BIN=/путь/llama-server`. Альтернатива без установки — вкладка «Свой сервер» (Ollama и др.).
- Для изображений: `pip install diffusers torch transformers accelerate safetensors`; скачайте diffusers-репозиторий (с `model_index.json`) или `.safetensors` чекпойнт.
- Файлы хранятся в `~/.kira-local` (`KIRA_LOCAL_DIR` меняет путь). Токен HF — поле в UI или `HF_TOKEN`.
- Сервер слушает только `127.0.0.1` — не открывайте его в сеть без авторизации.

Тесты: `pip install pytest pytest-asyncio && pytest`.
