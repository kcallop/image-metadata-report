#!/usr/bin/env python3
"""Plain-language EXIF report generator. Wraps exiftool and produces a PDF."""
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from xml.sax.saxutils import escape

from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

def _find_exiftool():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(base, "vendor", "exiftool", "bin", "exiftool")
    lib = os.path.join(base, "vendor", "exiftool", "lib", "perl5")
    if os.path.exists(script) and os.path.exists("/usr/bin/perl"):
        return ["/usr/bin/perl", "-I" + lib, script]
    found = shutil.which("exiftool") or "/opt/homebrew/bin/exiftool"
    return [found] if os.path.exists(found) else None


EXIFTOOL = _find_exiftool()

# GitHub "owner/repo" that publishes releases; the update check is hidden while this is empty.
UPDATE_REPO = "kcallop/image-metadata-report"
SETTINGS_PATH = os.path.expanduser("~/Library/Application Support/PhotoDetailsReport/settings.json")


def _app_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def app_version():
    try:
        with open(os.path.join(_app_dir(), "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "0"


def _vtuple(v):
    parts = []
    for p in v.lstrip("vV").split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f)


def check_for_updates(api_url=None):
    """Return (latest_version, download_url) if newer than this app, else None. Raises on failure."""
    import urllib.request
    url = api_url or f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "PhotoDetailsReport"})
    with urllib.request.urlopen(req, timeout=8) as r:
        rel = json.load(r)
    latest = rel["tag_name"].lstrip("vV")
    if _vtuple(latest) <= _vtuple(app_version()):
        return None
    dmg = next((a["browser_download_url"] for a in rel.get("assets", [])
                if a["name"].lower().endswith(".dmg")), None)
    return latest, dmg or rel["html_url"]

# (section title, intro text, [(tag, friendly label, explanation)])
SECTIONS = [
    ("Camera & Lens", "What device took this picture.", [
        ("Make", "Camera brand", ""),
        ("Model", "Camera model", ""),
        ("LensModel", "Lens", ""),
        ("LensMake", "Lens brand", ""),
        ("SerialNumber", "Camera serial number", "Can identify the specific camera that took the photo."),
        ("BodySerialNumber", "Camera serial number", "Can identify the specific camera that took the photo."),
        ("LensSerialNumber", "Lens serial number", ""),
        ("OwnerName", "Owner name", "A name stored in the camera settings."),
        ("CameraOwnerName", "Owner name", "A name stored in the camera settings."),
    ]),
    ("Date & Time", "When the picture was taken and changed.", [
        ("DateTimeOriginal", "Taken on", "When the shutter was pressed, per the camera's clock."),
        ("CreateDate", "Created on", ""),
        ("ModifyDate", "Last edited on", ""),
        ("OffsetTimeOriginal", "Time zone offset", "Difference from UTC at the time of capture."),
        ("SubSecTimeOriginal", "Fraction of a second", ""),
    ]),
    ("Shooting Settings", "How the camera was set up for this shot.", [
        ("ExposureTime", "Shutter speed", "How long the sensor was exposed to light. Shorter freezes motion."),
        ("FNumber", "Aperture", "Size of the lens opening (f-number). Lower = more light and blurrier background."),
        ("ISO", "ISO (light sensitivity)", "Higher values brighten dark scenes but add grain."),
        ("FocalLength", "Focal length", "How zoomed-in the shot is."),
        ("FocalLengthIn35mmFormat", "Focal length (35mm equivalent)", "Zoom level compared with a traditional film camera."),
        ("ExposureProgram", "Exposure mode", ""),
        ("ExposureCompensation", "Exposure adjustment", "Brightness correction applied by the photographer."),
        ("MeteringMode", "Light measuring mode", ""),
        ("Flash", "Flash", ""),
        ("WhiteBalance", "White balance", "How the camera corrected for the colour of the light."),
        ("LightSource", "Light source", ""),
        ("DigitalZoomRatio", "Digital zoom", ""),
        ("SceneCaptureType", "Scene type", ""),
        ("FocusMode", "Focus mode", ""),
    ]),
    ("Image", "Size and format of the picture itself.", [
        ("ImageWidth", "Width (pixels)", ""),
        ("ImageHeight", "Height (pixels)", ""),
        ("Megapixels", "Megapixels", "Total resolution in millions of pixels."),
        ("Orientation", "Orientation", ""),
        ("ColorSpace", "Colour space", ""),
        ("XResolution", "Print resolution (horizontal)", ""),
        ("YResolution", "Print resolution (vertical)", ""),
        ("ResolutionUnit", "Resolution unit", ""),
        ("BitsPerSample", "Bits per colour channel", ""),
        ("Compression", "Compression", ""),
    ]),
    ("Software & Editing", "Programs that created or changed the file.", [
        ("Software", "Software", "Camera firmware or editing program."),
        ("CreatorTool", "Created with", ""),
        ("HistorySoftwareAgent", "Edited with", ""),
        ("ProcessingSoftware", "Processed with", ""),
        ("Artist", "Photographer", ""),
        ("Creator", "Creator", ""),
        ("Copyright", "Copyright", ""),
        ("Rights", "Rights", ""),
        ("ImageDescription", "Description", ""),
        ("Title", "Title", ""),
        ("Description", "Description", ""),
        ("Keywords", "Keywords", ""),
        ("Subject", "Keywords", ""),
        ("UserComment", "Comment", ""),
    ]),
    ("File", "Details about the file on disk.", [
        ("FileName", "File name", ""),
        ("FileType", "File type", ""),
        ("MIMEType", "MIME type", ""),
        ("FileSize", "File size", ""),
        ("FileModifyDate", "File last modified", ""),
        ("FileCreateDate", "File created", ""),
    ]),
]

GPS_NOTE = ("Location data can reveal where a photo was taken, including home "
            "or workplace addresses. Think before sharing the original file.")


def run_exiftool(path):
    if not EXIFTOOL:
        raise RuntimeError("exiftool was not found. Install it with: brew install exiftool")
    base = EXIFTOOL + [ "-json", "-G0", "-a", "-struct", "-api", "largefilesupport=1"]
    out = subprocess.run(base + [path], capture_output=True, text=True)
    if out.returncode != 0 and not out.stdout:
        raise RuntimeError(out.stderr.strip() or "exiftool failed")
    pretty = json.loads(out.stdout)[0]
    raw = json.loads(subprocess.run(base + ["-n", path], capture_output=True, text=True).stdout)[0]
    return pretty, raw


def lookup(data, tag):
    """First value for tag across any group, preferring EXIF/XMP/File order."""
    for group in ("EXIF", "Composite", "XMP", "IPTC", "QuickTime", "File", "MakerNotes"):
        k = f"{group}:{tag}"
        if k in data and data[k] not in ("", None):
            return k, data[k]
    for k, v in data.items():
        if k.split(":", 1)[-1] == tag and v not in ("", None):
            return k, v
    return None, None


def fmt(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, dict):
        return ", ".join(f"{k}: {x}" for k, x in v.items())
    return str(v)


def build_rows(pretty, raw):
    """Return [(title, intro, [(label, value, note)])], gps dict or None, leftover count."""
    used, sections = set(), []
    for title, intro, fields in SECTIONS:
        rows, seen_labels = [], set()
        for tag, label, note in fields:
            key, val = lookup(pretty, tag)
            if key is None or label in seen_labels:
                continue
            used.add(key)
            seen_labels.add(label)
            v = fmt(val)
            if tag == "ExposureTime":
                _, r = lookup(raw, tag)
                if isinstance(r, (int, float)) and 0 < r < 1:
                    v = f"1/{round(1 / r)} sec"
            if tag == "FNumber" and not v.startswith("f/"):
                v = f"f/{v}"
            if tag == "FocalLength" and v.replace(".", "").isdigit():
                v += " mm"
            rows.append((label, v, note))
        if rows:
            sections.append((title, intro, rows))

    gps = None
    lat = raw.get("Composite:GPSLatitude")
    lon = raw.get("Composite:GPSLongitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        gps = {"lat": lat, "lon": lon}
        alt = raw.get("Composite:GPSAltitude")
        if isinstance(alt, (int, float)):
            gps["alt"] = alt
        for k in pretty:
            if k.startswith("Composite:GPS") or k.startswith("EXIF:GPS"):
                used.add(k)

    skip = ("SourceFile", "ExifTool:", "System:")
    leftover = [k for k in pretty if k not in used and not k.startswith(skip)]
    return sections, gps, len(leftover)


RAW_EXTS = {".nef", ".nrw", ".cr2", ".cr3", ".crw", ".arw", ".sr2", ".srf", ".dng", ".orf",
            ".rw2", ".raf", ".pef", ".srw", ".x3f", ".3fr", ".erf", ".mef", ".mrw", ".kdc", ".dcr"}


def _to_jpeg(im, max_px):
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return buf, im.size


def _embedded_previews(path):
    best = None
    for tag in ("-JpgFromRaw", "-PreviewImage", "-OtherImage", "-ThumbnailImage"):
        r = subprocess.run(EXIFTOOL + ["-b", tag, path], capture_output=True)
        if not r.stdout:
            continue
        try:
            with Image.open(io.BytesIO(r.stdout)) as im:
                im.load()
                if best is None or im.width * im.height > best.width * best.height:
                    best = im.copy()
        except Exception:
            continue
    return best


def make_preview(path, max_px=1600):
    if os.path.splitext(path)[1].lower() in RAW_EXTS:
        im = _embedded_previews(path)
        if im is not None:
            return _to_jpeg(im, max_px)
    try:
        with Image.open(path) as im:
            return _to_jpeg(im, max_px)
    except Exception:
        pass
    im = _embedded_previews(path)
    return _to_jpeg(im, max_px) if im is not None else (None, None)


def appendix(pretty, h2, intro_s):
    ss = getSampleStyleSheet()
    grp_s = ParagraphStyle("grp", parent=h2, fontSize=11, spaceBefore=10, spaceAfter=3)
    tag_s = ParagraphStyle("tag", parent=ss["Normal"], fontName="Courier-Bold", fontSize=7.5, leading=9.5)
    val_s = ParagraphStyle("tv", parent=ss["Normal"], fontName="Courier", fontSize=7.5, leading=9.5)
    groups = {}
    for k, v in pretty.items():
        if k == "SourceFile":
            continue
        g, _, t = k.partition(":")
        if not t:
            g, t = "Other", k
        groups.setdefault(g, []).append((t, fmt(v)))
    total = sum(len(v) for v in groups.values())
    out = [PageBreak(), Paragraph("Complete Technical Data", ParagraphStyle(
               "ah", parent=h2, fontSize=18, spaceBefore=0)),
           Paragraph(f"Every one of the {total} metadata entries found in this file, exactly as exiftool "
                     "reports them, grouped by where they are stored. This is the raw, unsimplified "
                     "data; the pages before this one are a summary of the most useful parts.", intro_s)]
    for g in sorted(groups, key=lambda x: (x != "EXIF", x)):
        rows = []
        for t, v in groups[g]:
            if len(v) > 600:
                v = v[:600] + f"... [{len(v) - 600} more characters not shown]"
            rows.append([Paragraph(escape(t), tag_s), Paragraph(escape(v).replace("\n", "<br/>"), val_s)])
        tbl = Table(rows, colWidths=[2.0 * inch, 4.9 * inch], repeatRows=0)
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f4f7fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        out += [Paragraph(f"{escape(g)} ({len(rows)})", grp_s), tbl]
    return out


def build_pdf(path, out_pdf):
    pretty, raw = run_exiftool(path)
    sections, gps, _ = build_rows(pretty, raw)

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=22, leading=28, alignment=0, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=ss["Normal"], textColor=colors.grey, fontSize=9)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#1f4e79"),
                        spaceBefore=14, spaceAfter=2)
    intro_s = ParagraphStyle("intro", parent=ss["Normal"], textColor=colors.grey, fontSize=9, spaceAfter=6)
    label_s = ParagraphStyle("label", parent=ss["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold")
    val_s = ParagraphStyle("val", parent=ss["Normal"], fontSize=10, leading=13)
    note_s = ParagraphStyle("note", parent=ss["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#666666"))
    warn_s = ParagraphStyle("warn", parent=ss["Normal"], fontSize=9, leading=12,
                            backColor=colors.HexColor("#fff4e5"), borderPadding=6,
                            borderColor=colors.HexColor("#f0a030"), borderWidth=0.5)

    def table(rows):
        data = []
        for label, value, note in rows:
            cell = [Paragraph(value if value.startswith('<link') else escape(value), val_s)]
            if note:
                cell.append(Paragraph(escape(note), note_s))
            data.append([Paragraph(escape(label), label_s), cell])
        t = Table(data, colWidths=[2.0 * inch, 4.9 * inch])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f4f7fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ]))
        return t

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.75 * inch, 0.5 * inch, f"Photo details report - {os.path.basename(path)}")
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    story = [Paragraph("Photo Details Report", h1),
             Paragraph(f"{escape(os.path.basename(path))} &nbsp;|&nbsp; generated "
                       f"{datetime.now():%B %d, %Y at %H:%M}", sub),
             Spacer(1, 10)]

    buf, size = make_preview(path)
    if buf:
        w, h = size
        scale = min(6.9 * inch / w, 4.6 * inch / h)
        story += [RLImage(buf, width=w * scale, height=h * scale, hAlign="CENTER"), Spacer(1, 6)]
    else:
        story.append(Paragraph("(A preview could not be generated for this file type.)", sub))

    if not sections and not gps:
        story.append(Paragraph("No metadata was found in this file. It may have been stripped "
                               "(common for images downloaded from social media or messaging apps).", val_s))

    if gps:
        lat, lon = gps["lat"], gps["lon"]
        rows = [("Coordinates", f"{abs(lat):.5f}° {'N' if lat >= 0 else 'S'}, "
                                f"{abs(lon):.5f}° {'E' if lon >= 0 else 'W'}", "")]
        if "alt" in gps:
            rows.append(("Altitude", f"{gps['alt']:.0f} m above sea level", ""))
        url = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
        rows.append(("Map link", f'<link href="{url}" color="blue">{url}</link>', ""))
        story.append(KeepTogether([Paragraph("Location", h2),
                                   Paragraph("Where the picture was taken, if the camera recorded it.", intro_s),
                                   Paragraph(f"<b>This photo contains GPS location data.</b> {GPS_NOTE}", warn_s),
                                   Spacer(1, 6), table(rows)]))
    else:
        story.append(KeepTogether([Paragraph("Location", h2),
                                   Paragraph("No GPS location data was found in this file.", val_s)]))

    for title, intro, rows in sections:
        story.append(KeepTogether([Paragraph(title, h2), Paragraph(intro, intro_s), table(rows)]))

    story += appendix(pretty, h2, intro_s)

    SimpleDocTemplate(out_pdf, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.8 * inch,
                      title="Photo Details Report").build(story, onFirstPage=footer, onLaterPages=footer)
    return out_pdf


def gui():
    import queue
    import threading
    import tkinter as tk
    import webbrowser
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("Photo Details Report")
    root.geometry("460x270" if UPDATE_REPO else "460x220")
    status = tk.StringVar(value="Choose a photo to create a readable PDF report.")
    settings = load_settings()
    results = queue.Queue()

    def pick():
        path = filedialog.askopenfilename(title="Choose a photo")
        if not path:
            return
        default = os.path.splitext(os.path.basename(path))[0] + " - details.pdf"
        out = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=default,
                                           filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        status.set("Working...")
        root.update_idletasks()
        try:
            build_pdf(path, out)
        except Exception as e:
            status.set("Something went wrong.")
            messagebox.showerror("Error", str(e))
            return
        status.set(f"Saved: {os.path.basename(out)}")
        subprocess.run(["open", out])

    def start_check(silent):
        def work():
            try:
                results.put((silent, check_for_updates(), None))
            except Exception as e:
                results.put((silent, None, e))
        threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            while True:
                silent, found, err = results.get_nowait()
                if err is not None:
                    if not silent:
                        messagebox.showinfo("Check for updates",
                                            "Couldn't check for updates. Please check your internet "
                                            "connection and try again.")
                elif found:
                    ver, url = found
                    if messagebox.askyesno("Update available",
                                           f"Version {ver} is available (you have {app_version()}).\n\n"
                                           "Download it now? Then open the downloaded file and drag the "
                                           "app into Applications, replacing the old one."):
                        webbrowser.open(url)
                elif not silent:
                    messagebox.showinfo("Check for updates",
                                        f"You're up to date (version {app_version()}).")
        except queue.Empty:
            pass
        root.after(300, poll)

    tk.Label(root, text="Photo Details Report", font=("Helvetica", 18, "bold")).pack(pady=(24, 6))
    tk.Label(root, textvariable=status, wraplength=400).pack(pady=6)
    tk.Button(root, text="Choose a photo...", command=pick, padx=16, pady=6).pack(pady=12)

    if UPDATE_REPO:
        auto = tk.BooleanVar(value=settings.get("auto_check", True))

        def toggle():
            settings["auto_check"] = auto.get()
            save_settings(settings)

        row = tk.Frame(root)
        row.pack(pady=4)
        tk.Button(row, text="Check for updates", command=lambda: start_check(False)).pack(side="left", padx=8)
        tk.Checkbutton(row, text="Check automatically when opened", variable=auto,
                       command=toggle).pack(side="left")
        tk.Label(root, text=f"Version {app_version()}", fg="grey").pack()
        poll()
        if auto.get():
            start_check(True)

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        src = sys.argv[1]
        dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + " - details.pdf"
        print(build_pdf(src, dst))
    else:
        gui()
