#!/bin/zsh
# Downloads the latest exiftool, swaps it into vendor/, and rebuilds the .app
set -euo pipefail
cd "$(dirname "$0")"

ver=$(curl -fsSL https://exiftool.org/ver.txt | tr -d '[:space:]')
current=$(/usr/bin/perl -Ivendor/exiftool/lib/perl5 vendor/exiftool/bin/exiftool -ver 2>/dev/null || echo none)
echo "Bundled: $current   Latest: $ver"
if [[ "$current" == "$ver" && "${1:-}" != "--force" ]]; then
  echo "Already up to date. (Use --force to rebuild anyway.)"; exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/et.tgz" "https://sourceforge.net/projects/exiftool/files/Image-ExifTool-$ver.tar.gz/download"
tar -xzf "$tmp/et.tgz" -C "$tmp"
src="$tmp/Image-ExifTool-$ver"
[[ -f "$src/exiftool" && -d "$src/lib" ]] || { echo "Unexpected archive layout"; exit 1; }

# Sanity check before replacing anything
[[ "$(/usr/bin/perl -I"$src/lib" "$src/exiftool" -ver)" == "$ver" ]] || { echo "Downloaded exiftool failed self-check"; exit 1; }

rm -rf vendor/exiftool
mkdir -p vendor/exiftool/bin vendor/exiftool/lib/perl5
cp "$src/exiftool" vendor/exiftool/bin/exiftool
cp -R "$src/lib/"* vendor/exiftool/lib/perl5/
cp "$src/README" vendor/exiftool/README

./build_app.sh
echo "Rebuilt dist/Photo Details Report.app with exiftool $ver"
