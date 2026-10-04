"""Lightweight frame-differencing motion detector.

Pipeline per sampled frame: grayscale -> Gaussian blur (denoise) -> absdiff
against previous frame -> binary threshold -> dilate (fill gaps) ->
contours filtered by minimum area. Only regions >= min_area count, which
rejects sensor noise and single-pixel flicker.

Motion alone never claims a person or threat; output is a motion score and
bounding boxes for the event metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class MotionBox:
    x: int
    y: int
    w: int
    h: int
    area: float


@dataclass
class MotionResult:
    motion: bool
    score: float  # motion pixel ratio in [0, 1]
    boxes: list[MotionBox] = field(default_factory=list)


class MotionDetector:
    def __init__(
        self,
        threshold: float = 25.0,
        min_area: float = 500.0,
        blur_kernel: int = 21,
    ) -> None:
        self.threshold = threshold
        self.min_area = min_area
        # GaussianBlur needs a positive odd kernel size.
        self.blur_kernel = max(3, int(blur_kernel) | 1)
        self._prev: Any = None

    def reset(self) -> None:
        self._prev = None

    def detect(self, frame: Any) -> MotionResult:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        if self._prev is None:
            self._prev = blurred
            return MotionResult(motion=False, score=0.0)
        delta = cv2.absdiff(self._prev, blurred)
        self._prev = blurred
        _, binary = cv2.threshold(delta, self.threshold, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [
            MotionBox(x=x, y=y, w=w, h=h, area=float(cv2.contourArea(c)))
            for c in contours
            for x, y, w, h in [cv2.boundingRect(c)]
            if float(cv2.contourArea(c)) >= self.min_area
        ]
        if not boxes:
            return MotionResult(motion=False, score=0.0)
        motion_pixels = int(np.count_nonzero(binary))
        total = binary.shape[0] * binary.shape[1]
        return MotionResult(motion=True, score=motion_pixels / total, boxes=boxes)


def confidence_for_score(score: float) -> float:
    """Map motion ratio to event confidence. Floor 0.35: motion is weak evidence."""
    return round(min(0.95, 0.35 + score * 4.0), 2)
