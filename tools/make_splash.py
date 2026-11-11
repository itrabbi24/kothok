"""Builds assets/splash.png - the startup banner PyInstaller shows the instant Kothok.exe is opened."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

W, H = 460, 230
img = Image.new("RGB", (W, H), "#0d1210")
d = ImageDraw.Draw(img)
d.rectangle([0, H - 6, W, H], fill="#006a4e")
img.paste(app.make_icon("idle", 96).convert("RGBA"), (34, 50), app.make_icon("idle", 96).convert("RGBA"))


def font(size, bold=False):
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


d.text((150, 52), "Kothok", font=font(40, True), fill="white")
d.text((152, 104), "Offline Bangla + English dictation", font=font(15), fill="#9fb5ab")
d.text((152, 128), f"v{app.VERSION}  •  rotexit.com", font=font(13), fill="#0f9d58")
img.save(ROOT / "assets" / "splash.png")
print("wrote assets/splash.png")
