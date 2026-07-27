"""
NexaTrans - Screenshot Module
Screen region capture using mss for fast, GPU-accelerated screenshots.
Handles DPI scaling: Qt logical coords -> physical pixels for capture.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.Screenshot")

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    logger.warning("mss not installed, falling back to PIL.ImageGrab")

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _get_dpr() -> float:
    """Get the primary screen device pixel ratio."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                return screen.devicePixelRatio()
    except Exception:
        pass
    return 1.0


def capture_region(region: dict) -> np.ndarray:
    """
    Capture a screen region and return as a numpy array (H, W, 3) in BGR format.

    The region coordinates are in Qt logical space and are converted to
    physical pixels using the screen's device pixel ratio.

    Args:
        region: {"x": int, "y": int, "width": int, "height": int} in logical coords.

    Returns:
        numpy.ndarray of shape (H, W, 3) in BGR format (physical pixels).
        Returns an empty array (0,0,3) on failure.
    """
    x = int(region.get("x", 0))
    y = int(region.get("y", 0))
    w = int(region.get("width", 0))
    h = int(region.get("height", 0))

    if w <= 0 or h <= 0:
        logger.warning(f"Invalid region dimensions: {w}x{h}")
        return np.empty((0, 0, 3), dtype=np.uint8)

    # Convert logical -> physical pixels (DPI scaling)
    dpr = _get_dpr()
    px = int(x * dpr)
    py = int(y * dpr)
    pw = int(w * dpr)
    ph = int(h * dpr)

    monitor = {"top": py, "left": px, "width": pw, "height": ph}

    try:
        if HAS_MSS:
            with mss.mss() as sct:
                img = sct.grab(monitor)
                frame = np.array(img)
                frame = frame[:, :, :3]
                logger.debug(
                    f"Screenshot: logical=({x},{y}) {w}x{h} "
                    f"-> physical=({px},{py}) {pw}x{ph} (DPR={dpr})"
                )
                return frame
        elif HAS_PIL:
            bbox = (px, py, px + pw, py + ph)
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            frame = np.array(img)
            frame = frame[:, :, ::-1].copy()
            logger.debug(
                f"Screenshot (PIL): logical=({x},{y}) {w}x{h} "
                f"-> physical=({px},{py}) {pw}x{ph}"
            )
            return frame
        else:
            logger.error("No screenshot backend available. Install mss or Pillow.")
            return np.empty((0, 0, 3), dtype=np.uint8)
    except Exception as e:
        logger.error(f"Screenshot capture failed: {e}", exc_info=True)
        return np.empty((0, 0, 3), dtype=np.uint8)
