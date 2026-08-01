"""
NexaTrans - Layout Analyzer (Stage 4)
Analyzes reading direction of text boxes: horizontal (left->right) or vertical (top->bottom).
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.LayoutAnalyzer")


class LayoutAnalyzer:
    """Determine text reading direction for each box."""

    def analyze(self, boxes: list) -> list:
        """
        Analyze reading direction for each text box.

        Args:
            boxes: List of [x1,y1, x2,y2, x3,y3, x4,y4].

        Returns:
            List of dicts: [{"id": N, "direction": "horizontal"|"vertical", "box": [...]}, ...]
        """
        if not boxes:
            return []

        results = []

        try:
            for i, box in enumerate(boxes):
                if len(box) < 8:
                    continue

                xs = [box[j] for j in range(0, len(box), 2)]
                ys = [box[j + 1] for j in range(0, len(box), 2)]

                w = max(xs) - min(xs)
                h = max(ys) - min(ys)

                # If width >= height, horizontal; otherwise vertical
                direction = "horizontal" if w >= h else "vertical"

                results.append({
                    "id": i + 1,
                    "direction": direction,
                    "box": box,
                })

            h_count = sum(1 for r in results if r["direction"] == "horizontal")
            v_count = len(results) - h_count
            logger.debug(
                f"Layout analysis: {h_count} horizontal, {v_count} vertical"
            )
            return results

        except Exception as e:
            logger.error(f"Layout analysis failed: {e}", exc_info=True)
            return []
