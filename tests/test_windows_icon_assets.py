from pathlib import Path

from PIL import Image, ImageChops

from scripts.build_windows_icons import (
    APP_ICO,
    APP_PNG,
    ICON_SIZES,
    SETUP_ICO,
    SETUP_PNG,
    build_icon_assets,
)


def _ico_sizes(path: Path) -> set[tuple[int, int]]:
    with Image.open(path) as image:
        return set(image.ico.sizes())


def test_tracked_windows_icons_are_complete_and_distinct():
    for png_path in (APP_PNG, SETUP_PNG):
        with Image.open(png_path) as image:
            assert image.mode == "RGBA"
            assert image.size == (1024, 1024)
            assert image.getpixel((0, 0))[3] == 0
            assert image.getpixel((512, 512))[3] == 255

    assert _ico_sizes(APP_ICO) == set(ICON_SIZES)
    assert _ico_sizes(SETUP_ICO) == set(ICON_SIZES)
    assert APP_ICO.read_bytes() != SETUP_ICO.read_bytes()


def test_tracked_windows_icons_match_the_canonical_svg(tmp_path):
    generated = build_icon_assets(
        app_png=tmp_path / APP_PNG.name,
        app_ico=tmp_path / APP_ICO.name,
        setup_png=tmp_path / SETUP_PNG.name,
        setup_ico=tmp_path / SETUP_ICO.name,
    )

    tracked = (APP_PNG, APP_ICO, SETUP_PNG, SETUP_ICO)
    for generated_path, tracked_path in zip(generated, tracked, strict=True):
        with (
            Image.open(generated_path) as generated_image,
            Image.open(tracked_path) as tracked_image,
        ):
            if generated_path.suffix.casefold() == ".ico":
                for size in ICON_SIZES:
                    generated_frame = generated_image.ico.getimage(size).convert("RGBA")
                    tracked_frame = tracked_image.ico.getimage(size).convert("RGBA")
                    assert ImageChops.difference(
                        generated_frame, tracked_frame
                    ).getbbox() is None
            else:
                assert ImageChops.difference(
                    generated_image.convert("RGBA"), tracked_image.convert("RGBA")
                ).getbbox() is None
