#!/bin/sh
# Exercise the package scripts against a fake DSM layout. Usage: tools/test.sh
set -eu

cd "$(dirname "$0")/.."
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

mkdir -p "$T/css" "$T/target" "$T/var"
cp -R src/package/. "$T/target/"
printf '.x-window{color:#000}\n' > "$T/css/desktop.css"
gzip -9 -k "$T/css/desktop.css"
ORIG=$(cat "$T/css/desktop.css")

export DARKMODE_PKG_DIR="$T/target" DARKMODE_VAR_DIR="$T/var" DARKMODE_CSS_DIR="$T/css" DARKMODE_SKIP_ROOT_CHECK=1
export SYNOPKG_PKGDEST="$T/target" SYNOPKG_PKGVAR="$T/var" SYNOPKG_TEMP_LOGFILE="$T/log"
DM="sh $T/target/bin/darkmode"

# Install with the "always" wizard choice, then start.
wizard_mode_always=true sh src/scripts/postinst
[ "$(cat "$T/var/mode")" = always ] || fail "mode not saved"
sh src/scripts/start-stop-status start
grep -q 'one-time setup' "$T/log" || fail "missing setup hint before apply"
sh src/scripts/start-stop-status status || fail "status should be running"
cmp -s "$T/target/ui/dark.css" src/package/share/dark.css || fail "theme not served"

# Apply twice: one import line, gz in sync, original rules kept.
$DM apply >/dev/null
$DM apply >/dev/null
[ "$(grep -c DSM-DARKMODE "$T/css/desktop.css")" = 1 ] || fail "apply not idempotent"
head -n 1 "$T/css/desktop.css" | grep -q '^/\*DSM-DARKMODE\*/@import url("/webman/3rdparty/DarkMode/dark.css");$' || fail "import not first"
gzip -dc "$T/css/desktop.css.gz" | cmp -s - "$T/css/desktop.css" || fail "gz out of sync"
cmp -s "$T/var/backup/desktop.css" - <<X || fail "backup wrong"
$ORIG
X
$DM status | grep -q '^hooked' || fail "status should say hooked"
rm "$T/log"; sh src/scripts/start-stop-status start
[ ! -e "$T/log" ] || fail "setup hint shown after apply"

# Stop empties the theme; start in auto mode wraps it in a media query.
sh src/scripts/start-stop-status stop
grep -q '{' "$T/target/ui/dark.css" && fail "theme still served when stopped"
sh src/scripts/start-stop-status status && fail "status should be stopped"
echo auto > "$T/var/mode"
sh src/scripts/start-stop-status start
head -n 1 "$T/target/ui/dark.css" | grep -q 'prefers-color-scheme: dark' || fail "auto mode not wrapped"

# Upgrade keeps the saved mode.
sh src/scripts/postinst
[ "$(cat "$T/var/mode")" = auto ] || fail "upgrade reset mode"

# Revert restores the file and gz byte for byte.
$DM revert >/dev/null
[ "$(cat "$T/css/desktop.css")" = "$ORIG" ] || fail "revert did not restore"
gzip -dc "$T/css/desktop.css.gz" | cmp -s - "$T/css/desktop.css" || fail "gz out of sync after revert"
ls "$T/css" | grep -q darkmode && fail "temp files left behind"

# @charset must stay first.
printf '@charset "UTF-8";\n.a{}\n' > "$T/css/desktop.css"
$DM apply >/dev/null
head -n 1 "$T/css/desktop.css" | grep -q '^@charset' || fail "@charset moved"
sed -n 2p "$T/css/desktop.css" | grep -q DSM-DARKMODE || fail "import not after @charset"

# Root is required without the test override; missing file is an error.
env -u DARKMODE_SKIP_ROOT_CHECK sh "$T/target/bin/darkmode" apply >/dev/null 2>&1 && [ "$(id -u)" != 0 ] && fail "ran without root"
rm "$T/css/desktop.css"
$DM apply 2>/dev/null && fail "apply succeeded with no stylesheet"

for j in src/WIZARD_UIFILES/install_uifile src/package/ui/config src/conf/privilege; do
    python3 -m json.tool "$j" >/dev/null || fail "bad JSON: $j"
done

echo "all tests passed"
