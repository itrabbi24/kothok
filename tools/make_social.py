"""Render assets/social-preview.png (1280x640) for the GitHub repo's social preview."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

W, H = 1280, 640
img = Image.new("RGB", (W, H), "#0d1210")
d = ImageDraw.Draw(img)
for r, a in ((520, 18), (380, 28), (240, 40)):  # soft green glow behind the logo
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((300 - r, 320 - r, 300 + r, 320 + r), fill=(15, 157, 88, a))
    img.paste(glow, (0, 0), glow)
logo = app.make_icon("idle", 300)
img.paste(logo, (150, 170), logo)
fonts = "C:/Windows/Fonts/"
bn = ImageFont.truetype(fonts + "Nirmala.ttc", 96, index=1)
big = ImageFont.truetype(fonts + "segoeuib.ttf", 92)
mid = ImageFont.truetype(fonts + "segoeui.ttf", 38)
small = ImageFont.truetype(fonts + "seguisb.ttf", 28)
d.text((520, 160), "কথক", font=bn, fill="#eef1f6")
d.text((520, 268), "Kothok", font=big, fill="#0f9d58")
d.text((522, 392), "Offline Bangla + English voice typing", font=mid, fill="#eef1f6")
d.text((522, 442), "for Windows · free & open source", font=mid, fill="#8b93a5")
d.text((522, 530), "rotexit.com", font=small, fill="#f42a41")
img.save(ROOT / "assets" / "social-preview.png")
print("written")
