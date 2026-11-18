#!/bin/zsh
# Builds dist/Photo Details Report.app from the current source and vendor/exiftool
set -euo pipefail
cd "$(dirname "$0")"
version=$(<VERSION)

.venv/bin/pyinstaller --noconfirm --windowed --name "Photo Details Report" \
  --add-data "vendor:vendor" --add-data "VERSION:." --collect-all pillow_heif \
  --icon packaging/AppIcon.icns \
  --osx-bundle-identifier com.local.photodetailsreport exif_report.py >/dev/null 2>&1

app="dist/Photo Details Report.app"
plist="$app/Contents/Info.plist"
for key in CFBundleShortVersionString CFBundleVersion; do
  /usr/libexec/PlistBuddy -c "Set :$key $version" "$plist" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :$key string $version" "$plist"
done
codesign --force --deep -s - "$app" >/dev/null 2>&1   # ad-hoc re-sign after editing the plist
echo "Built $app (v$version)"
