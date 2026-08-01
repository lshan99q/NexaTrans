import json
from PySide6.QtWidgets import QApplication

app = QApplication()

config = json.load(open("config/settings.json"))
region = config["region"]
print(f"Region (logical): x={region['x']}, y={region['y']}, {region['width']}x{region['height']}")

dpr = app.primaryScreen().devicePixelRatio()
print(f"DPR: {dpr}")

from screen.screenshot import capture_region
img = capture_region(region)
print(f"Screenshot (physical): {img.shape[1]}x{img.shape[0]}")

expected_w = int(region['width'] * dpr)
expected_h = int(region['height'] * dpr)
match = img.shape[1] == expected_w and img.shape[0] == expected_h
print(f"Expected: {expected_w}x{expected_h} -> {'MATCH' if match else 'MISMATCH'}")

if match:
    print("\nDPI fix verified! Screenshot correctly scaled to physical pixels.")
else:
    print(f"\nSTILL WRONG: got {img.shape[1]}x{img.shape[0]}, expected {expected_w}x{expected_h}")

app.quit()
