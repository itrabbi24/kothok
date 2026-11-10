"""Render assets/social-preview.png (1280x640) for the GitHub repo's social preview."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

W, H = 1280, 640
# light poster (the first version was dark - see git history)
img = Image.new("RGB", (W, H), "#f6f8f7")
d = ImageDraw.Draw(img)
for r, a in ((470, 22), (330, 34), (210, 48)):  # soft green glow behind the logo
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((300 - r, 320 - r, 300 + r, 320 + r), fill=(15, 157, 88, a))
    img.paste(glow, (0, 0), glow)
d.rectangle((0, H - 14, W, H), fill="#006a4e")  # flag-green base line
logo = app.make_icon("idle", 300)
img.paste(logo, (150, 170), logo)
fonts = "C:/Windows/Fonts/"
bn = ImageFont.truetype(fonts + "Nirmala.ttc", 96, index=1)
big = ImageFont.truetype(fonts + "segoeuib.ttf", 92)
mid = ImageFont.truetype(fonts + "segoeui.ttf", 38)
small = ImageFont.truetype(fonts + "segoeui.ttf", 26)
small_b = ImageFont.truetype(fonts + "segoeuib.ttf", 26)
d.text((520, 150), "কথক", font=bn, fill="#14201b")
d.text((520, 258), "Kothok", font=big, fill="#0b8a4c")
d.text((522, 384), "Offline Bangla + English voice typing", font=mid, fill="#14201b")
d.text((522, 434), "for Windows · free & open source", font=mid, fill="#5f6b66")
label = "Developed by "
d.text((522, 528), label, font=small, fill="#5f6b66")
d.text((522 + d.textlength(label, font=small), 528), "rotexit.com", font=small_b, fill="#006a4e")
img.save(ROOT / "assets" / "social-preview.png")
print("written")
