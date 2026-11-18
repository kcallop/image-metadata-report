#!/bin/zsh
# Builds dist/PhotoDetailsReport-<version>.dmg (unsigned) from dist/Photo Details Report.app
set -euo pipefail
cd "$(dirname "$0")"
version=$(<VERSION)
[[ "${1:-}" == "--skip-build" ]] || ./build_app.sh

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp -R "dist/Photo Details Report.app" "$stage/"
ln -s /Applications "$stage/Applications"
cp packaging/HOW_TO_OPEN.txt "$stage/How to open (read me first).txt"

out="dist/PhotoDetailsReport-$version.dmg"
rm -f "$out"
hdiutil create -quiet -volname "Photo Details Report" -srcfolder "$stage" -fs HFS+ -format UDZO "$out"
echo "Created $out ($(du -h "$out" | cut -f1))"
