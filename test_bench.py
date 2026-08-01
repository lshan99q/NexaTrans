import json, logging, time
logging.basicConfig(level=logging.WARNING)

config = json.load(open("config/settings.json"))
region = config["region"]
from screen.screenshot import capture_region
img = capture_region(region)
print(f"Image: {img.shape[1]}x{img.shape[0]}")

from detection.dbnet_detector import DBNetDetector

for limit in [640, 480, 320]:
    detector = DBNetDetector(limit_side_len=limit)
    times = []
    nboxes = 0
    for i in range(5):
        t0 = time.time()
        boxes = detector.detect(img)
        dt = (time.time() - t0) * 1000
        times.append(dt)
        nboxes = len(boxes)
        if i == 0 and boxes:
            b = boxes[0]
            print(f"  Box example: [{b[0]},{b[1]} ... {b[6]},{b[7]}]")
    avg = sum(times) / len(times)
    fps = 1000 / avg if avg > 0 else 0
    print(f"  limit={limit}: {avg:.0f}ms ({fps:.1f} FPS), {nboxes} boxes")
