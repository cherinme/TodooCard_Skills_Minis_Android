#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$script_dir/../android-bridge" && pwd)"
output="${1:-$script_dir/../assets/todoocard-android-bridge.apk}"
sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"

if [[ -z "$sdk_root" && -d /opt/homebrew/share/android-commandlinetools ]]; then
  sdk_root=/opt/homebrew/share/android-commandlinetools
fi
command -v gradle >/dev/null 2>&1 || {
  echo "gradle is required to build the Android companion." >&2
  exit 69
}
java_home="${JAVA_HOME:-}"
if [[ -d /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home ]]; then
  java_home=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
elif command -v /usr/libexec/java_home >/dev/null 2>&1; then
  java_home="$(/usr/libexec/java_home -v 17 2>/dev/null || true)"
fi
[[ -n "$java_home" && -x "$java_home/bin/java" ]] || {
  echo "JDK 17 is required to build the Android companion." >&2
  exit 69
}
[[ -n "$sdk_root" && -d "$sdk_root/platforms" ]] || {
  echo "Set ANDROID_SDK_ROOT to an Android SDK containing platforms/." >&2
  exit 69
}

build_root="$(mktemp -d /tmp/todoocard-android-build.XXXXXX)"
trap 'rm -rf "$build_root"' EXIT
cp -R "$project_dir/." "$build_root/project"
printf 'sdk.dir=%s\n' "$sdk_root" > "$build_root/project/local.properties"
JAVA_HOME="$java_home" GRADLE_USER_HOME="${GRADLE_USER_HOME:-$HOME/.gradle}" \
  gradle --no-daemon -p "$build_root/project" lintDebug assembleDebug
mkdir -p "$(dirname "$output")"
cp "$build_root/project/app/build/outputs/apk/debug/app-debug.apk" "$output"
echo "$output"
