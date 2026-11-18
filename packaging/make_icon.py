import os, subprocess, sys
from PIL import Image, ImageDraw

S = 1024
im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
# background gradient clipped to rounded square
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line([(0, y), (S, y)], fill=(int(40 + 20 * t), int(110 + 30 * t), int(200 - 30 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((60, 60, S - 60, S - 60), radius=210, fill=255)
im.paste(grad, (0, 0), mask)
# document card
d.rounded_rectangle((250, 190, 774, 834), radius=40, fill=(255, 255, 255, 255))
# photo thumbnail on the card
d.rounded_rectangle((300, 240, 724, 470), radius=22, fill=(170, 205, 245, 255))
d.polygon([(300, 470), (470, 330), (590, 430), (650, 380), (724, 450), (724, 470)], fill=(60, 130, 90, 255))
d.ellipse((620, 270, 680, 330), fill=(255, 215, 90, 255))
# text lines
for i, w in enumerate((424, 360, 400, 300, 380)):
    y = 520 + i * 55
    d.rounded_rectangle((300, y, 300 + w, y + 22), radius=11, fill=(60, 80, 110, 255) if i % 2 == 0 else (150, 165, 185, 255))

out = sys.argv[1]
iconset = out + ".iconset"
os.makedirs(iconset, exist_ok=True)
for size in (16, 32, 128, 256, 512):
    im.resize((size, size), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}.png")
    im.resize((size * 2, size * 2), Image.LANCZOS).save(f"{iconset}/icon_{size}x{size}@2x.png")
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
