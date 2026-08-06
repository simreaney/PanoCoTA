"""Pillow graph renderer fallback."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import build_x_ticks, scale_points_for_canvas


def generate_with_pillow(
    output_path: Path,
    x_values: list,
    y_values: list[float],
    y_axis_label: str,
    x_is_datetime: bool,
    animate: bool,
    size: str = "m",
    animation_speed: float = 1.0,
) -> None:
    """Render a static PNG or animated GIF graph with Pillow."""
    size_to_canvas = {
        "s": (1280, 720),
        "m": (1600, 900),
        "l": (1920, 1080),
    }
    width, height = size_to_canvas.get(size, size_to_canvas["m"])
    left_pad = 180
    right_pad = 62
    top_pad = 62
    bottom_pad = 62

    points, y_min, y_max = scale_points_for_canvas(
        x_values,
        y_values,
        width,
        height,
        left_pad=left_pad,
        right_pad=right_pad,
        top_pad=top_pad,
        bottom_pad=bottom_pad,
    )
    x_ticks = build_x_ticks(x_values, points, x_is_datetime)

    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        meta_font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    def draw_frame(upto: int | None = None) -> Image.Image:
        """Draw a frame containing optional partial line progression."""
        img = Image.new("RGB", (width, height), "#101416")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (width - 1, height - 1)], outline="#334")
        draw.line([(left_pad, top_pad), (left_pad, height - bottom_pad)], fill="#455", width=2)
        draw.line(
            [(left_pad, height - bottom_pad), (width - right_pad, height - bottom_pad)],
            fill="#455",
            width=2,
        )

        y_label_img = Image.new("RGBA", (220, 40), (0, 0, 0, 0))
        y_label_draw = ImageDraw.Draw(y_label_img)
        y_label_draw.text((0, 0), y_axis_label, fill="#dde", font=title_font)
        y_label_rot = y_label_img.rotate(90, expand=True)
        img.paste(y_label_rot, (10, int((height - y_label_rot.height) / 2)), y_label_rot)

        y_tick_count = 5
        for i in range(y_tick_count):
            ratio = i / (y_tick_count - 1)
            y_pos = (height - bottom_pad) - (ratio * (height - (top_pad + bottom_pad)))
            y_value = y_min + (ratio * (y_max - y_min))
            draw.line([(left_pad - 8, y_pos), (left_pad, y_pos)], fill="#667", width=1)
            draw.text((96, y_pos - 12), f"{y_value:.2f}", fill="#99a", font=meta_font)

        for x_pos, tick_label in x_ticks:
            draw.line(
                [(x_pos, height - bottom_pad), (x_pos, height - (bottom_pad - 8))],
                fill="#667",
                width=1,
            )
            if "\n" in tick_label:
                top, bottom = tick_label.split("\n", 1)
                draw.text((x_pos - 62, height - (bottom_pad - 14)), top, fill="#99a", font=meta_font)
                draw.text((x_pos - 42, height - (bottom_pad - 36)), bottom, fill="#99a", font=meta_font)
            else:
                draw.text((x_pos - 20, height - (bottom_pad - 18)), tick_label, fill="#99a", font=meta_font)

        visible = points if upto is None else points[:upto]
        if len(visible) >= 2:
            draw.line(visible, fill="#e84855", width=5)
        if visible:
            x, y = visible[-1]
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill="#ffd9dd")
        return img

    if not animate:
        draw_frame().save(output_path, format="PNG")
        return

    max_frames = 180
    step = max(1, len(points) // max_frames)
    frames = [draw_frame(idx) for idx in range(1, len(points) + 1, step)]
    if not frames:
        frames.append(draw_frame(1))

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=max(20, int(80 / max(animation_speed, 0.25))),
        loop=0,
        format="GIF",
    )
