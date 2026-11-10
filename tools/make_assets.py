"""Render the PNG / ICO versions of the Kothok logo (same drawing as app.make_icon)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

out = ROOT / "assets"
out.mkdir(exist_ok=True)
big = app.make_icon("idle", 256)
big.save(out / "kothok.png")
app.make_icon("idle", 1024).save(out / "kothok-1024.png")
big.save(out / "kothok.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("assets written to", out)
