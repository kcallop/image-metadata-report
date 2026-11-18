# Image Metadata Report

A Mac app that turns a photo into a readable PDF: a preview, plain-language camera and settings info, GPS location (with a privacy warning), and a complete technical appendix. Powered by [ExifTool](https://exiftool.org) by Phil Harvey.

**Download:** get the latest `.dmg` from the [Releases page](../../releases/latest). Requires Apple Silicon and macOS 14+. The app is unsigned; the guide inside the disk image explains the one-time right-click > Open step.

Everything runs locally; no photos are uploaded.

## Building

```
python3 -m venv .venv && .venv/bin/pip install reportlab pillow pillow-heif certifi pyinstaller
./update_exiftool.sh      # refresh bundled exiftool and build the app
./build_dmg.sh            # create dist/PhotoDetailsReport-<version>.dmg
```

Or double-click `Update and Build.command`.
