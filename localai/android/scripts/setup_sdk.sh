#!/usr/bin/env bash
# Готовит Android SDK для Gradle: local.properties и лицензии. Нужен на CI (Codemagic), где SDK уже установлен.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$SDK" || ! -d "$SDK" ]]; then
  echo "!! Не найден Android SDK (ANDROID_SDK_ROOT / ANDROID_HOME)" >&2
  exit 1
fi
echo "sdk.dir=$SDK" > "$HERE/../local.properties"
SDKMANAGER="$(command -v sdkmanager || ls "$SDK"/cmdline-tools/*/bin/sdkmanager 2>/dev/null | tail -1 || true)"
if [[ -n "$SDKMANAGER" ]]; then
  yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true
fi
echo ">> Android SDK: $SDK"
