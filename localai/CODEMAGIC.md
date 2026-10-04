# Сборка APK в Codemagic

В корне репозитория лежит `codemagic.yaml` — Codemagic подхватит его сам.

## Быстрый старт (APK без подписи keystore)

1. Зайдите на [codemagic.io](https://codemagic.io) → **Add application** → выберите GitHub → репозиторий `Tishir614/Kira-core-`.
2. Тип проекта: **Other / Android** → когда спросят про конфигурацию, выберите **codemagic.yaml** (а не Workflow Editor).
3. Выберите ветку `claude/local-ai-chat-app-9gg4go` (или `main`, после слияния) и workflow **Kira Local — APK** → **Start new build**.
4. Через ~10–15 минут (первая сборка; llama.cpp собирается ~10 мин) на странице сборки в **Artifacts** появится `KiraLocal.apk`. Скачайте и установите на телефон (arm64, Android 8+).

Последующие сборки быстрее: Gradle-кэш и собранный `llama-server` берутся из кэша Codemagic.

## Что делает сборка

| Шаг | Что происходит |
|---|---|
| Подготовка Android SDK | пишет `local.properties`, принимает лицензии |
| Тесты | Node-тесты разбора ссылок/поиска/Markdown и JVM-тесты локального сервера |
| Сборка llama-server | `localai/android/scripts/build_llama.sh` компилирует llama.cpp (NDK, arm64) и кладёт как `libllama_server.so` |
| Сборка APK | `./gradlew :app:assembleRelease` (Gradle 8.9 через wrapper, Java 17) |

`versionCode` берётся из номера сборки Codemagic (`BUILD_NUMBER`) — новую версию можно ставить поверх старой.

## Подписанный релиз (по желанию)

1. Codemagic → **Teams → Code signing identities → Android keystores** → загрузите keystore (или сгенерируйте) и задайте имя ссылки **`kira_keystore`**.
2. Запустите workflow **Kira Local — подписанные APK + AAB**: получите подписанный APK и `.aab` (для Google Play).

## Настройка

- **Версия llama.cpp:** переменная `LLAMA_REF` в `codemagic.yaml` (ветка или тег; для воспроизводимых сборок лучше зафиксировать тег). Чтобы пересобрать `llama-server` в обход кэша, добавьте при запуске переменную `LLAMA_REBUILD=1`.
- **Запуск по пушу:** workflow `kira-local-apk` стартует на push в `main` и `claude/*`. Если нужен только ручной запуск, удалите блок `triggering`.
- **Уведомления:** при желании добавьте в workflow блок `publishing: email: recipients: [ваш@email]`.
- **Машина:** `instance_type: linux_x2`. Если сборка не укладывается в лимит минут бесплатного плана, оставьте только workflow `kira-local-apk`.

## Локальная сборка

```bash
cd localai/android
bash scripts/setup_sdk.sh      # нужен Android SDK (ANDROID_SDK_ROOT)
bash scripts/build_llama.sh    # нужен NDK; при отсутствии ставится через sdkmanager
./gradlew :app:assembleRelease
```
