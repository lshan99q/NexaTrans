"""
NexaTrans - Text Renderer (Stage 5)
Renders OCR text onto images using PIL ImageDraw for overlay display.
"""

import logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("NexaTrans.Renderer")

FONT_SEARCH = [
    "msgothic.ttc", "msmincho.ttc", "yumindb.ttf",
    "simhei.ttf", "simsun.ttc", "msyh.ttc", "msyhbd.ttf",
    "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf",
]


class TextRenderer:
    """Render text as RGBA images for overlay compositing."""

    def __init__(self, font_size: int = 16, font_path: str = None):
        self._font_size = font_size
        self._font = self._load_font(font_path, font_size)

    def _load_font(self, path: str, size: int) -> ImageFont.FreeTypeFont:
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

        for name in FONT_SEARCH:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue

        try:
            return ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, v: int):
        if v != self._font_size:
            self._font_size = v
            self._font = self._load_font(None, v)

    def render(
        self,
        text: str,
        width: int,
        height: int,
        color: tuple = (255, 255, 255),
        bg_alpha: int = 0,
    ) -> np.ndarray:
        """
        Render text to an RGBA image.

        Args:
            text: Text string to render.
            width: Image width (px).
            height: Image height (px).
            color: Text RGB color.
            bg_alpha: Background alpha (0 = transparent, 255 = opaque).

        Returns:
            RGBA image as numpy array (H, W, 4) uint8.
        """
        if width <= 0 or height <= 0:
            return np.zeros((16, 16, 4), dtype=np.uint8)

        img = Image.new("RGBA", (width, height), (0, 0, 0, bg_alpha))
        draw = ImageDraw.Draw(img)

        bbox = draw.textbbox((0, 0), text, font=self._font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if tw > width:
            scale = width / tw
            scaled_size = max(8, int(self._font_size * scale))
            try:
                font = ImageFont.truetype(self._font.path if hasattr(self._font, "path") else "arial.ttf", scaled_size)
            except Exception:
                font = self._font
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        else:
            font = self._font

        x = max(0, (width - tw) // 2 - bbox[0])
        y = max(0, (height - th) // 2 - bbox[1])

        draw.text((x, y), text, font=font, fill=color + (255,))

        return np.array(img, dtype=np.uint8)
