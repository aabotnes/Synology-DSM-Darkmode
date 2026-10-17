#!/bin/sh
# Build dist/DarkMode-<version>.spk from src/. Usage: tools/build.sh [version]
set -eu

cd "$(dirname "$0")/.."
VERSION=${1:-$(cat VERSION)}
SRC=src
OUT=dist
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Reproducible, root-owned archives.
TAR_OPTS="--owner=0 --group=0 --numeric-owner --sort=name --mtime=@0"

tar $TAR_OPTS --exclude=__pycache__ -czf "$WORK/package.tgz" -C "$SRC/package" .

CHECKSUM=$(md5sum "$WORK/package.tgz" | cut -d' ' -f1)
EXTRACTSIZE=$(du -sk "$SRC/package" | cut -f1)
sed -e "s/@VERSION@/$VERSION/" \
    -e "s/@CHECKSUM@/$CHECKSUM/" \
    -e "s/@EXTRACTSIZE@/$EXTRACTSIZE/" \
    "$SRC/INFO.in" > "$WORK/INFO"

cp -R "$SRC/conf" "$SRC/scripts" "$SRC/WIZARD_UIFILES" "$WORK/"
cp "$SRC/PACKAGE_ICON.PNG" "$SRC/PACKAGE_ICON_256.PNG" "$WORK/"
chmod 755 "$WORK"/scripts/*

mkdir -p "$OUT"
SPK="$OUT/DarkMode-$VERSION.spk"
tar $TAR_OPTS -cf "$SPK" -C "$WORK" \
    INFO package.tgz conf scripts WIZARD_UIFILES PACKAGE_ICON.PNG PACKAGE_ICON_256.PNG
echo "$SPK"
