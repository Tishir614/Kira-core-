#!/usr/bin/env bash
# Собирает llama-server (llama.cpp) для Android arm64 и кладёт его как libllama_server.so в jniLibs приложения.
# Используется и в Codemagic, и в GitHub Actions. Результат кэшируется (CACHE_DIR), чтобы не собирать каждый раз.
#
# Переменные окружения (все необязательны):
#   LLAMA_REF      ветка/тег llama.cpp (по умолчанию master)
#   LLAMA_REBUILD  =1 — игнорировать кэш
#   CACHE_DIR      каталог кэша (по умолчанию ~/.cache/kira-llama)
#   ANDROID_NDK_ROOT / ANDROID_NDK_HOME / ANDROID_NDK_LATEST_HOME — путь к NDK; если не найден, ставится через sdkmanager
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-$HERE/../app/src/main/jniLibs/arm64-v8a}"
REF="${LLAMA_REF:-master}"
CACHE_DIR="${CACHE_DIR:-$HOME/.cache/kira-llama}"
NDK_VERSION="26.3.11579264"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
KEY="$(echo "$REF" | tr '/ ' '__')"
CACHED="$CACHE_DIR/libllama_server.$KEY.so"

mkdir -p "$OUT_DIR" "$CACHE_DIR"

if [[ -f "$CACHED" && "${LLAMA_REBUILD:-0}" != "1" ]]; then
  echo ">> llama-server ($REF) взят из кэша"
  cp "$CACHED" "$OUT_DIR/libllama_server.so"
  ls -lh "$OUT_DIR"
  exit 0
fi

# --- NDK ---
NDK="${ANDROID_NDK_ROOT:-${ANDROID_NDK_HOME:-${ANDROID_NDK_LATEST_HOME:-}}}"
if [[ -z "$NDK" || ! -f "$NDK/build/cmake/android.toolchain.cmake" ]]; then
  NDK=""
  if [[ -n "$SDK" ]]; then NDK="$(ls -d "$SDK"/ndk/* 2>/dev/null | sort -V | tail -1 || true)"; fi
fi
if [[ -z "$NDK" || ! -f "$NDK/build/cmake/android.toolchain.cmake" ]]; then
  echo ">> NDK не найден — устанавливаю $NDK_VERSION через sdkmanager"
  SDKMANAGER="$(command -v sdkmanager || ls "$SDK"/cmdline-tools/*/bin/sdkmanager 2>/dev/null | tail -1)"
  yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" "ndk;$NDK_VERSION"
  NDK="$SDK/ndk/$NDK_VERSION"
fi
echo ">> NDK: $NDK"

# --- cmake ---
CMAKE="$(command -v cmake || true)"
if [[ -z "$CMAKE" && -n "$SDK" ]]; then CMAKE="$(ls "$SDK"/cmake/*/bin/cmake 2>/dev/null | sort -V | tail -1 || true)"; fi
if [[ -z "$CMAKE" ]]; then
  SDKMANAGER="$(command -v sdkmanager || ls "$SDK"/cmdline-tools/*/bin/sdkmanager 2>/dev/null | tail -1)"
  "$SDKMANAGER" "cmake;3.22.1"
  CMAKE="$SDK/cmake/3.22.1/bin/cmake"
fi
echo ">> cmake: $CMAKE"

# --- сборка ---
SRC="$(mktemp -d)/llama.cpp"
BUILD="$(mktemp -d)"
git clone --depth 1 --branch "$REF" https://github.com/ggml-org/llama.cpp "$SRC"
echo ">> llama.cpp: $(git -C "$SRC" rev-parse --short HEAD)"

ARCH="-march=armv8.2-a+dotprod"
"$CMAKE" -S "$SRC" -B "$BUILD" \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 -DANDROID_STL=c++_static \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_OPENMP=OFF -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF \
  -DCMAKE_C_FLAGS="$ARCH" -DCMAKE_CXX_FLAGS="$ARCH"
"$CMAKE" --build "$BUILD" --target llama-server -j"$(nproc 2>/dev/null || echo 4)"

BIN="$BUILD/bin/llama-server"
[[ -f "$BIN" ]] || { echo "!! llama-server не собрался" >&2; exit 1; }
"$NDK"/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip "$BIN" || true

cp "$BIN" "$CACHED"
cp "$BIN" "$OUT_DIR/libllama_server.so"
ls -lh "$OUT_DIR"
