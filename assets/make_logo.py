"""Generates assets/logo.png (1024x1024), the bot's Telegram profile picture.

Telegram crops profile pictures to a circle, so everything important stays
inside the centered circle. Drawn at 4x and downscaled for anti-aliasing.

Usage: python assets/make_logo.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
SCALE = 4
CANVAS = SIZE * SCALE

# Palette
GRADIENT_TOP = (15, 32, 39)       # deep blue-green
GRADIENT_BOTTOM = (44, 83, 100)   # lighter teal-blue
PERSON_FRONT = (255, 255, 255)
PERSON_BACK = (159, 179, 200)
ACCENT = (53, 224, 194)           # teal: detection brackets


def s(value: float) -> int:
    return round(value * SCALE)


def vertical_gradient(draw: ImageDraw.ImageDraw) -> None:
    for y in range(CANVAS):
        t = y / CANVAS
        color = tuple(
            round(top + (bottom - top) * t)
            for top, bottom in zip(GRADIENT_TOP, GRADIENT_BOTTOM, strict=True)
        )
        draw.line([(0, y), (CANVAS, y)], fill=color)


def person(draw: ImageDraw.ImageDraw, cx: float, head_cy: float,
           head_r: float, torso_w: float, torso_top: float,
           torso_bottom: float, color: tuple) -> None:
    """Head circle + bust with rounded shoulders and a flat base."""
    draw.ellipse(
        [s(cx - head_r), s(head_cy - head_r), s(cx + head_r), s(head_cy + head_r)],
        fill=color,
    )
    draw.rounded_rectangle(
        [s(cx - torso_w / 2), s(torso_top), s(cx + torso_w / 2), s(torso_bottom)],
        radius=s(torso_w / 2),
        corners=(True, True, False, False),
        fill=color,
    )


def corner_brackets(draw: ImageDraw.ImageDraw, box: tuple, length: float,
                    width: float, color: tuple) -> None:
    """Four L-shaped viewfinder corners around `box` (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    radius = s(width / 2)
    for cx, horizontal_dx in ((x0, 1), (x1, -1)):
        for cy, vertical_dy in ((y0, 1), (y1, -1)):
            draw.rounded_rectangle(
                [s(min(cx, cx + horizontal_dx * length)), s(cy - width / 2),
                 s(max(cx, cx + horizontal_dx * length)), s(cy + width / 2)],
                radius=radius, fill=color,
            )
            draw.rounded_rectangle(
                [s(cx - width / 2), s(min(cy, cy + vertical_dy * length)),
                 s(cx + width / 2), s(max(cy, cy + vertical_dy * length))],
                radius=radius, fill=color,
            )


def main() -> None:
    image = Image.new("RGB", (CANVAS, CANVAS))
    draw = ImageDraw.Draw(image)

    vertical_gradient(draw)

    # Back row first, front person on top
    person(draw, cx=318, head_cy=436, head_r=62,
           torso_w=210, torso_top=530, torso_bottom=770, color=PERSON_BACK)
    person(draw, cx=706, head_cy=436, head_r=62,
           torso_w=210, torso_top=530, torso_bottom=770, color=PERSON_BACK)
    person(draw, cx=512, head_cy=396, head_r=86,
           torso_w=300, torso_top=512, torso_bottom=790, color=PERSON_FRONT)

    corner_brackets(draw, box=(180, 190, 844, 824), length=115, width=30,
                    color=ACCENT)

    image = image.resize((SIZE, SIZE), Image.LANCZOS)
    output = Path(__file__).parent / "logo.png"
    image.save(output)
    print(f"Saved {output} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
