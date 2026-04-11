"""
Run this script once to generate assets/icon.ico and assets/icon.png.
Requires Pillow: pip install Pillow
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate_icon():
    assets_dir = Path(__file__).parent
    size = 256

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill="#2D7DD2",
    )

    # Inner circle (darker)
    inner_margin = 40
    draw.ellipse(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        fill="#1a5fa8",
    )

    # Clock hands (simple tracker icon)
    cx, cy = size // 2, size // 2
    r = size // 2 - 50

    # Hour ticks
    import math
    for i in range(12):
        angle = math.radians(i * 30 - 90)
        x1 = cx + int((r - 6) * math.cos(angle))
        y1 = cy + int((r - 6) * math.sin(angle))
        x2 = cx + int(r * math.cos(angle))
        y2 = cy + int(r * math.sin(angle))
        draw.line([x1, y1, x2, y2], fill="white", width=3)

    # Minute hand
    angle = math.radians(90 - 90)  # pointing right (3 o'clock → productivity)
    draw.line(
        [cx, cy,
         cx + int((r - 20) * math.cos(angle)),
         cy + int((r - 20) * math.sin(angle))],
        fill="white", width=5,
    )

    # Hour hand
    angle = math.radians(45 - 90)
    draw.line(
        [cx, cy,
         cx + int((r - 35) * math.cos(angle)),
         cy + int((r - 35) * math.sin(angle))],
        fill="#aaddff", width=7,
    )

    # Center dot
    dot_r = 8
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill="white")

    # Save PNG
    png_path = assets_dir / "icon.png"
    img.save(str(png_path), "PNG")
    print(f"Saved {png_path}")

    # Save ICO (multiple sizes)
    ico_path = assets_dir / "icon.ico"
    sizes = [16, 32, 48, 64, 128, 256]
    icons = []
    for s in sizes:
        icons.append(img.resize((s, s), Image.LANCZOS))
    icons[0].save(
        str(ico_path), format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=icons[1:],
    )
    print(f"Saved {ico_path}")


if __name__ == "__main__":
    generate_icon()
