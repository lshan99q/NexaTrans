"""
NexaTrans - Text Merger (Stage 4)
Merges nearby DBNet boxes that likely belong to the same text line.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.TextMerger")


class TextMerger:
    """Merge nearby text boxes based on spatial proximity and height similarity."""

    def __init__(self, merge_distance: int = 20, height_ratio: float = 0.6):
        """
        Args:
            merge_distance: Max horizontal gap (px) between boxes to merge.
            height_ratio: Max height difference ratio (0-1) to consider same line.
        """
        self._merge_distance = merge_distance
        self._height_ratio = height_ratio

    @property
    def merge_distance(self) -> int:
        return self._merge_distance

    @property
    def height_ratio(self) -> float:
        return self._height_ratio

    def merge(self, boxes: list) -> list:
        """
        Merge nearby text boxes.

        Args:
            boxes: List of [x1,y1, x2,y2, x3,y3, x4,y4] in logical coordinates.

        Returns:
            Merged boxes as axis-aligned [x1,y1, x2,y2, x3,y3, x4,y4].
        """
        if not boxes or len(boxes) <= 1:
            return boxes

        try:
            # Convert to axis-aligned rects for easier comparison
            rects = []
            for box in boxes:
                if len(box) < 8:
                    continue
                xs = [box[i] for i in range(0, len(box), 2)]
                ys = [box[i + 1] for i in range(0, len(box), 2)]
                rects.append({
                    "x1": min(xs), "y1": min(ys),
                    "x2": max(xs), "y2": max(ys),
                    "w": max(xs) - min(xs),
                    "h": max(ys) - min(ys),
                })

            if not rects:
                return boxes

            # Sort by y1 then x1 (top-to-bottom, left-to-right)
            rects.sort(key=lambda r: (r["y1"], r["x1"]))

            merged = [rects[0]]
            used = {0}

            for i in range(1, len(rects)):
                if i in used:
                    continue

                r = rects[i]
                found_merge = False

                for j, m in enumerate(merged):
                    # Check horizontal proximity
                    gap_x = r["x1"] - m["x2"]
                    gap_y = abs(r["y1"] - m["y1"])
                    overlap_y = max(0, min(r["y2"], m["y2"]) - max(r["y1"], m["y1"]))
                    height_similar = (
                        min(r["h"], m["h"]) / max(r["h"], m["h"], 1)
                        >= self._height_ratio
                    )

                    # Same line: close horizontally, overlapping vertically, similar height
                    if (
                        gap_x >= 0
                        and gap_x <= self._merge_distance
                        and gap_y <= max(r["h"], m["h"]) * 0.5
                        and height_similar
                    ):
                        # Merge into existing
                        merged[j] = {
                            "x1": min(m["x1"], r["x1"]),
                            "y1": min(m["y1"], r["y1"]),
                            "x2": max(m["x2"], r["x2"]),
                            "y2": max(m["y2"], r["y2"]),
                            "w": max(m["x2"], r["x2"]) - min(m["x1"], r["x1"]),
                            "h": max(m["y2"], r["y2"]) - min(m["y1"], r["y1"]),
                        }
                        used.add(i)
                        found_merge = True
                        break

                if not found_merge:
                    merged.append(r)
                    used.add(i)

            # Convert back to axis-aligned quads
            result = []
            for m in merged:
                result.append([
                    m["x1"], m["y1"],
                    m["x2"], m["y1"],
                    m["x2"], m["y2"],
                    m["x1"], m["y2"],
                ])

            logger.debug(f"Merged {len(boxes)} boxes -> {len(result)} regions")
            return result

        except Exception as e:
            logger.error(f"Text merging failed: {e}", exc_info=True)
            return boxes
