#!/bin/zsh
# Double-click to refresh exiftool, rebuild the app and create the .dmg.
cd "$(dirname "$0")"
echo "=== Photo Details Report: update and build ==="
echo "Current app version: $(<VERSION)"
read "newver?New app version number (press Enter to keep it the same): "
[[ -n "$newver" ]] && echo "$newver" > VERSION

if ./update_exiftool.sh --force && ./build_dmg.sh --skip-build; then
  echo; echo "Done. Your installer is in the 'dist' folder."
  open dist
else
  echo; echo "Something went wrong - see the messages above."
fi
echo; read -k 1 "?Press any key to close this window."
