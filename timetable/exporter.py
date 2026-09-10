from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import DAYS, TimetableProject


class ExportError(RuntimeError):
    pass


def desktop_directory() -> Path:
    """兼容中文/重定向桌面的 Windows 路径解析。"""
    if os.name == "nt":
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(260)
            # CSIDL_DESKTOPDIRECTORY = 0x10
            result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buffer)
            if result == 0 and buffer.value:
                return Path(buffer.value)
        except (AttributeError, OSError):
            pass
    return Path.home() / "Desktop"


def default_export_path(today: date | None = None) -> Path:
    today = today or date.today()
    return desktop_directory() / f"课表_{today:%Y-%m-%d}.png"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / ("msyhbd.ttc" if bold else "msyh.ttc"),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / ("simhei.ttf" if bold else "simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _contrast_text(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    try:
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return "#FFFFFF"
    return "#1F2937" if (r * 299 + g * 587 + b * 114) / 1000 > 168 else "#FFFFFF"


def export_project_png(project: TimetableProject, destination: Path) -> Path:
    if not project.periods:
        raise ExportError("请至少添加一个节次后再导出。")
    scale = 2
    label_width, day_width = 170 * scale, 210 * scale
    header_height, row_height = 84 * scale, 126 * scale
    margin = 34 * scale
    width = margin * 2 + label_width + day_width * 7
    height = margin * 2 + header_height + row_height * len(project.periods)
    image = Image.new("RGB", (width, height), "#F6F8FC")
    draw = ImageDraw.Draw(image)
    font_header = _font(22 * scale, bold=True)
    font_period = _font(17 * scale, bold=True)
    font_time = _font(13 * scale)
    font_course = _font(17 * scale, bold=True)
    font_detail = _font(12 * scale)

    left, top = margin, margin
    draw.rounded_rectangle((left, top, width - margin, height - margin), 18 * scale, fill="#FFFFFF")
    for column, day in enumerate(("时间 / 节次", *DAYS)):
        x0 = left if column == 0 else left + label_width + (column - 1) * day_width
        x1 = left + label_width if column == 0 else x0 + day_width
        draw.rectangle((x0, top, x1, top + header_height), fill="#EEF3FF")
        box = draw.textbbox((0, 0), day, font=font_header)
        draw.text(((x0 + x1 - box[2]) / 2, top + (header_height - box[3]) / 2), day, font=font_header, fill="#24324A")

    for row, period in enumerate(project.periods):
        y0 = top + header_height + row * row_height
        y1 = y0 + row_height
        fill = "#FAFBFD" if row % 2 == 0 else "#FFFFFF"
        draw.rectangle((left, y0, width - margin, y1), fill=fill)
        box = draw.textbbox((0, 0), period.name, font=font_period)
        draw.text((left + (label_width - box[2]) / 2, y0 + 25 * scale), period.name, font=font_period, fill="#25324B")
        time_text = f"{period.start_time} - {period.end_time}"
        box = draw.textbbox((0, 0), time_text, font=font_time)
        draw.text((left + (label_width - box[2]) / 2, y0 + 65 * scale), time_text, font=font_time, fill="#72809A")

    grid_color = "#DCE3EF"
    for x in [left, left + label_width, *[left + label_width + i * day_width for i in range(1, 8)]]:
        draw.line((x, top, x, height - margin), fill=grid_color, width=2)
    for row in range(len(project.periods) + 1):
        y = top + header_height + row * row_height
        draw.line((left, y, width - margin, y), fill=grid_color, width=2)

    for placement in project.placements:
        course = project.course_by_id(placement.course_id)
        if course is None or not (0 <= placement.day < 7) or placement.period >= len(project.periods):
            continue
        actual_duration = min(course.duration, len(project.periods) - placement.period)
        x0 = left + label_width + placement.day * day_width + 8 * scale
        y0 = top + header_height + placement.period * row_height + 8 * scale
        x1 = x0 + day_width - 16 * scale
        y1 = y0 + actual_duration * row_height - 16 * scale
        fill = course.color if course.color.startswith("#") and len(course.color) == 7 else "#5B8FF9"
        draw.rounded_rectangle((x0, y0, x1, y1), 13 * scale, fill=fill)
        color = _contrast_text(fill)
        max_chars = 13
        name = course.name if len(course.name) <= max_chars else course.name[: max_chars - 1] + "…"
        lines = [name, course.location or "地点未填写", course.week_rule.label()]
        fonts = [font_course, font_detail, font_detail]
        y = y0 + 15 * scale
        for text, font in zip(lines, fonts):
            draw.text((x0 + 13 * scale, y), text, font=font, fill=color)
            y += (31 if font is font_course else 25) * scale

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "PNG", optimize=True, dpi=(192, 192))
    except OSError as exc:
        raise ExportError(f"导出 PNG 失败：{exc}") from exc
    return destination
