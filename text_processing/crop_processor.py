"""
NexaTrans - Crop Processor (Stage 4)
Crops text regions from the image using merged boxes.
Outputs (image_crop, mask_crop) pairs for OCR input.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.CropProcessor")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class CropProcessor:
    """Crop text regions from source image for OCR input."""

    def crop(
        self,
        image: np.ndarray,
        boxes: list,
        mask: np.ndarray = None,
        padding: int = 2,
    ) -> list:
        """
        Crop text regions from the image.

        Args:
            image: Source image (H, W, 3) in BGR format.
            boxes: List of axis-aligned boxes [x1,y1, x2,y2, x3,y3, x4,y4].
            mask: Optional full-image mask (H, W). If provided, also crops mask.
            padding: Extra pixels to add around each crop.

        Returns:
            List of dicts: [{"image": ndarray, "box": list, "mask": ndarray|None}, ...]
        """
        h, w = image.shape[:2]

        if not boxes:
            return []

        results = []

        try:
            for i, box in enumerate(boxes):
                if len(box) < 8:
                    continue

                xs = [box[j] for j in range(0, len(box), 2)]
                ys = [box[j + 1] for j in range(0, len(box), 2)]

                x1 = max(0, min(xs) - padding)
                y1 = max(0, min(ys) - padding)
                x2 = min(w, max(xs) + padding)
                y2 = min(h, max(ys) + padding)

                if x2 <= x1 or y2 <= y1:
                    continue

                crop_img = image[y1:y2, x1:x2].copy()

                crop_mask = None
                if mask is not None and mask.size > 0:
                    crop_mask = mask[y1:y2, x1:x2].copy()

                results.append({
                    "id": i + 1,
                    "box": [x1, y1, x2, y1, x2, y2, x1, y2],
                    "image": crop_img,
                    "mask": crop_mask,
                })

            logger.debug(f"Cropped {len(results)} text regions")
            return results

        except Exception as e:
            logger.error(f"Crop processing failed: {e}", exc_info=True)
            return []
