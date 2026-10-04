"""Generate a small synthetic test video. Run: python scripts/generate_test_video.py [out]."""

import sys

import cv2
import numpy as np

W, H, N = 320, 240, 60
dest = sys.argv[1] if len(sys.argv) > 1 else "test_video.mp4"
out = cv2.VideoWriter(dest, cv2.VideoWriter_fourcc(*"mp4v"), 10, (W, H))
for i in range(N):
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    x = int((i / N) * (W - 40))
    cv2.rectangle(frame, (x, 90), (x + 40, 130), (255, 255, 255), -1)
    out.write(frame)
out.release()
print(f"wrote {dest}")
