"""Draw the package icons (a crescent moon on a dark tile). Run once; the PNGs are committed."""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def icon(size):
    s = size * 4  # supersample, then shrink for smooth edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 5, fill=(32, 36, 48, 255))
    r = s * 0.30
    cx, cy = s * 0.5, s * 0.5
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 214, 120, 255))
    ox, oy = cx + r * 0.45, cy - r * 0.35
    d.ellipse([ox - r, oy - r, ox + r, oy + r], fill=(32, 36, 48, 255))
    return img.resize((size, size), Image.LANCZOS)


def main():
    for size in (16, 24, 32, 48, 64, 72, 256):
        icon(size).save(os.path.join(ROOT, "package", "ui", "images", f"icon_{size}.png"))
    icon(64).save(os.path.join(ROOT, "PACKAGE_ICON.PNG"))
    icon(256).save(os.path.join(ROOT, "PACKAGE_ICON_256.PNG"))


if __name__ == "__main__":
    sys.exit(main())
