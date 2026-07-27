"""
NexaTrans - Mask Generator (Stage 4)
Converts DBNet polygon boxes to pixel-level binary masks using OpenCV.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.MaskGenerator")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class MaskGenerator:
    """Generate binary masks from DBNet polygon boxes."""

    def generate(self, image_size: tuple, polygons: list) -> np.ndarray:
        """
        Convert polygon boxes to a pixel-level binary mask.

        Args:
            image_size: (height, width) of the source image.
            polygons: List of boxes, each as [x1,y1, x2,y2, x3,y3, x4,y4].

        Returns:
            Binary mask (H, W) as uint8, values 0 or 255.
        """
        h, w = image_size[:2]

        if not HAS_CV2:
            logger.error("OpenCV not available for mask generation")
            return np.zeros((h, w), dtype=np.uint8)

        mask = np.zeros((h, w), dtype=np.uint8)

        if not polygons:
            return mask

        try:
            for box in polygons:
                if len(box) < 8:
                    continue

                pts = np.array([
                    [box[0], box[1]],
                    [box[2], box[3]],
                    [box[4], box[5]],
                    [box[6], box[7]],
                ], dtype=np.int32)

                cv2.fillPoly(mask, [pts], 255)

            logger.debug(f"Generated mask: {np.count_nonzero(mask)} pixels from {len(polygons)} polygons")
            return mask

        except Exception as e:
            logger.error(f"Mask generation failed: {e}", exc_info=True)
            return np.zeros((h, w), dtype=np.uint8)
