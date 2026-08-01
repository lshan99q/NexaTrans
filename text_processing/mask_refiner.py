"""
NexaTrans - Mask Refiner (Stage 4)
Dilates and smooths binary masks for better text coverage and soft edges.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.MaskRefiner")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class MaskRefiner:
    """Refine binary masks: dilate to expand, blur to soften edges."""

    def __init__(self, dilate_size: int = 5, blur_size: int = 3):
        """
        Args:
            dilate_size: Kernel size for morphological dilation (odd, 3-15).
            blur_size: Kernel size for Gaussian blur (odd, 3-15).
        """
        self._dilate_size = max(3, min(dilate_size, 15))
        if self._dilate_size % 2 == 0:
            self._dilate_size += 1

        self._blur_size = max(3, min(blur_size, 15))
        if self._blur_size % 2 == 0:
            self._blur_size += 1

        self._dilate_kernel = None
        self._init_kernels()

    def _init_kernels(self):
        """Pre-create kernels for reuse."""
        if HAS_CV2:
            self._dilate_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (self._dilate_size, self._dilate_size)
            )

    @property
    def dilate_size(self) -> int:
        return self._dilate_size

    @property
    def blur_size(self) -> int:
        return self._blur_size

    def refine(self, mask: np.ndarray) -> np.ndarray:
        """
        Refine a binary mask: dilate then blur.

        Args:
            mask: Binary mask (H, W) uint8, values 0 or 255.

        Returns:
            Refined mask (H, W) uint8, 0-255 with soft edges.
        """
        if not HAS_CV2:
            logger.error("OpenCV not available for mask refinement")
            return mask

        if mask is None or mask.size == 0:
            return mask

        try:
            # Step 1: Morphological dilation
            dilated = cv2.dilate(mask, self._dilate_kernel, iterations=1)

            # Step 2: Gaussian blur for soft edges
            refined = cv2.GaussianBlur(dilated, (self._blur_size, self._blur_size), 0)

            logger.debug(
                f"Mask refined: dilate={self._dilate_size}px, blur={self._blur_size}px"
            )
            return refined

        except Exception as e:
            logger.error(f"Mask refinement failed: {e}", exc_info=True)
            return mask
