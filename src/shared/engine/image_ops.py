"""
image_ops — 图片操作工具

Pillow 图片缩放/水印叠加/格式转换。
依赖 Pillow（可选：不安装时仅提供占位实现）。
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


def resize_image(
    src: str | Path,
    dst: str | Path,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    quality: int = 95,
) -> Path:
    """等比缩放图片（保持宽高比）。"""
    if not HAS_PILLOW:
        raise RuntimeError("Pillow 未安装，无法处理图片")

    img = Image.open(str(src))
    w, h = img.size

    if max_width and w > max_width:
        ratio = max_width / w
        w, h = max_width, int(h * ratio)
    if max_height and h > max_height:
        ratio = max_height / h
        w, h = int(w * ratio), max_height

    img = img.resize((w, h), Image.LANCZOS)
    out = Path(dst)
    img.save(str(out), quality=quality)
    return out


def add_text_watermark(
    src: str | Path,
    dst: str | Path,
    text: str,
    *,
    opacity: int = 50,
    font_size: int = 36,
    angle: int = -30,
) -> Path:
    """添加文字水印。"""
    if not HAS_PILLOW:
        raise RuntimeError("Pillow 未安装")

    img = Image.open(str(src)).convert("RGBA")
    w, h = img.size

    # 创建水印层
    watermark = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 平铺水印
    text_bbox = draw.textbbox((0, 0), text, font=font)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]

    step_x = tw + 100
    step_y = th + 100

    for x in range(0, w + step_x, step_x):
        for y in range(0, h + step_y, step_y):
            draw.text(
                (x, y), text,
                fill=(128, 128, 128, opacity),
                font=font,
            )

    watermark = watermark.rotate(angle, expand=False, center=(w // 2, h // 2))
    result = Image.alpha_composite(img, watermark)
    result = result.convert("RGB")

    out = Path(dst)
    result.save(str(out), quality=95)
    return out


def convert_format(
    src: str | Path,
    dst: str | Path,
    *,
    target_format: str = "PNG",
    quality: int = 95,
) -> Path:
    """转换图片格式。"""
    if not HAS_PILLOW:
        raise RuntimeError("Pillow 未安装")

    img = Image.open(str(src))
    if target_format.upper() in ("JPEG", "JPG") and img.mode == "RGBA":
        img = img.convert("RGB")

    out = Path(dst)
    img.save(str(out), format=target_format, quality=quality)
    return out


def get_image_size(path: str | Path) -> tuple[int, int] | None:
    """获取图片尺寸 (width, height)。"""
    if not HAS_PILLOW:
        return None
    try:
        with Image.open(str(path)) as img:
            return img.size
    except Exception:
        return None
