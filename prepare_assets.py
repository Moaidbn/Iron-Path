"""Clean chroma-key residue from generated game assets.

The asset prompts deliberately exclude green from the characters and fortresses, so a
conservative green-key pass can safely turn the generator's temporary key background
into transparent pixels. This is a post-generation cleanup only; it never redraws
or changes the intended subjects.
"""
from pathlib import Path
from PIL import Image
import numpy as np

ASSET_DIR = Path(__file__).parent / "static" / "assets"
PATTERNS = ("portrait_*.png", "fortress_*.png")


def clean_green_key(path: Path) -> None:
    image = Image.open(path).convert("RGBA")
    pixels = np.asarray(image).copy()
    rgb = pixels[:, :, :3].astype(np.int16)
    alpha = pixels[:, :, 3]
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    # Fully remove unmistakable key green. The art brief excludes green assets.
    hard = (green > 70) & (green > red * 1.28) & (green > blue * 1.28)
    # Suppress only the thin green fringe left at alpha edges.
    soft = (~hard) & (green > 55) & (green > red + 18) & (green > blue + 18)
    alpha[hard] = 0
    alpha[soft] = np.minimum(alpha[soft], 70)
    pixels[:, :, 3] = alpha
    Image.fromarray(pixels, "RGBA").save(path, optimize=True)
    print(f"cleaned {path.name}")


if __name__ == "__main__":
    paths = sorted({p for pattern in PATTERNS for p in ASSET_DIR.glob(pattern)})
    if not paths:
        raise SystemExit("No generated assets found")
    for asset_path in paths:
        clean_green_key(asset_path)
    print(f"processed {len(paths)} assets")
